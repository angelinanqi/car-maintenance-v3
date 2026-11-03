"""Public-web URL validation shared by the credential-free capture helper."""
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class UnsafeURL(ValueError):
    pass


def public_ip(value):
    address = ipaddress.ip_address(value)
    if (not address.is_global or address.is_multicast or address.is_reserved
            or address == ipaddress.ip_address('168.63.129.16')):
        raise UnsafeURL('Only public internet addresses may be captured.')
    return address


def public_url(value, *, keep_fragment=False):
    try:
        parts = urlsplit(value)
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.port not in {None, 80, 443}
                or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value):
            raise ValueError()
        host = parts.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            public_ip(host)
        display = f'[{host}]' if ':' in host else host
        return urlunsplit((parts.scheme, display + (f':{parts.port}' if parts.port else ''),
                           parts.path or '/', parts.query, parts.fragment if keep_fragment else ''))
    except (ValueError, UnicodeError):
        raise UnsafeURL('Enter a public HTTP or HTTPS URL using port 80 or 443.') from None


def resolve_public(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise OSError('The website has no public address.')
    for record in addresses:
        public_ip(record[4][0])
    return addresses
