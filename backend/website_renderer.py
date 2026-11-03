"""Credential-free rendering child. Inputs arrive as JSON on stdin, never shell code."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
from io import BytesIO
import math
import json
import os
import re
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from shared.public_web import public_url, UnsafeURL
from backend.services.capture_proxy import capture_proxy


class CaptureError(Exception):
    def __init__(self, code, message, retryable=False):
        self.code, self.retryable = code, retryable
        super().__init__(message)


def validate_pdf(path, max_bytes, max_pages):
    from pypdf import PdfReader
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise CaptureError('pdf_size', 'The PDF is empty or exceeds the document size limit.')
    try:
        reader = PdfReader(path)
        if reader.is_encrypted or not 0 < len(reader.pages) <= max_pages:
            raise CaptureError('pdf_pages', f'The PDF must contain 1–{max_pages} readable pages.')
        count = len(reader.pages)
        text = ' '.join((page.extract_text() or '') for page in reader.pages)
    except CaptureError:
        raise
    except Exception as error:
        raise CaptureError('invalid_pdf', 'The generated PDF could not be opened.') from error
    return count, text


def remaining_ms(deadline, maximum=30000):
    value = min(maximum, int((deadline - time.monotonic()) * 1000))
    if value <= 0:
        raise CaptureError('timeout', 'The page exceeded the capture time limit.', True)
    return value


def capture(url, options, output, limits):
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout, Error as BrowserError
    url = public_url(url, keep_fragment=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + limits['timeout']
    warnings = []
    browser_path = limits.get('browser_path')
    if browser_path:
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browser_path
    try:
        with capture_proxy(deadline, limits['network_bytes']) as proxy, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, chromium_sandbox=True,
                proxy={'server': f'http://127.0.0.1:{proxy.server_address[1]}', 'bypass': '<-loopback>'},
                args=['--disable-quic', '--disable-background-networking', '--disable-extensions',
                      '--disable-component-update', '--dns-prefetch-disable',
                      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'])
            try:
                context = browser.new_context(viewport={'width': 1280, 'height': 900},
                    service_workers='block', accept_downloads=False, ignore_https_errors=False)
                # Every HTTP destination is resolved and pinned by the proxy.
                def route_request(route):
                    try:
                        public_url(route.request.url)
                        if route.request.resource_type == 'image':
                            # Preserve image content at up to ~300 dpi across an
                            # A4 page. Huge originals otherwise produce PDFs that
                            # exceed upload limits even when displayed small.
                            response = route.fetch(timeout=remaining_ms(deadline), max_redirects=6)
                            data = response.body()
                            mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
                            if response.status == 200 and mime.startswith('image/') and mime != 'image/svg+xml':
                                from PIL import Image, ImageOps
                                try:
                                    with Image.open(BytesIO(data)) as original:
                                        if original.width * original.height > 40_000_000:
                                            warnings.append('An oversized image could not be captured. Review the original illustration.')
                                            route.abort('blockedbyclient')
                                            return
                                        ratio = min(1, 2560 / original.width, 10000 / original.height,
                                                    math.sqrt(12_000_000 / (original.width * original.height)))
                                        if ratio < 1:
                                            warnings.append('Large source images were resized for PDF capture. Check fine illustration details.')
                                            image = ImageOps.exif_transpose(original)
                                            image.thumbnail((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), Image.Resampling.LANCZOS)
                                            encoded = BytesIO()
                                            if original.format == 'JPEG':
                                                image.convert('RGB').save(encoded, format='JPEG', quality=90)
                                                mime = 'image/jpeg'
                                            else:
                                                image.save(encoded, format='PNG')
                                                mime = 'image/png'
                                            headers = {key: value for key,value in response.headers.items()
                                                       if key not in {'content-type','content-length','content-encoding'}}
                                            route.fulfill(response=response, body=encoded.getvalue(), content_type=mime, headers=headers)
                                            return
                                except (OSError, ValueError, Image.DecompressionBombError):
                                    pass  # A supported browser image may use a format Pillow cannot decode.
                            route.fulfill(response=response)
                            return
                        route.continue_()
                    except UnsafeURL:
                        route.abort('blockedbyclient')
                    except (BrowserError, OSError):
                        warnings.append('A page resource could not be loaded. Check the PDF before publication.')
                        route.abort('failed')
                context.route('**/*', route_request)
                context.route_web_socket('**/*', lambda ws: ws.close())
                page = context.new_page()
                rules_page = context.new_page()
                context.on('page', lambda popup: popup.close() if popup not in (page, rules_page) else None)
                page.on('dialog', lambda dialog: dialog.dismiss())
                page.set_default_timeout(10000)
                # Use Chromium's transport for rules too. Cache per origin and
                # recheck the final path, including redirects to another origin.
                rule_cache = {}
                def check_access(target):
                    parts = urlsplit(target)
                    origin = (parts.scheme, parts.netloc)
                    if origin not in rule_cache:
                        robots_url = urlunsplit((*origin, '/robots.txt', '', ''))
                        response = rules_page.goto(robots_url, wait_until='domcontentloaded', timeout=remaining_ms(deadline))
                        if response is None or response.status == 429 or response.status >= 500:
                            raise CaptureError('robots_unavailable', 'The website’s access rules are temporarily unavailable.', True)
                        if response.status in {401, 403}:
                            raise CaptureError('access_denied', 'This website does not allow automated capture. Upload a PDF saved from your browser.')
                        rules = RobotFileParser()
                        if response.status == 200:
                            data = response.body()
                            if len(data) > 262144:
                                raise CaptureError('robots_unavailable', 'The website returned an oversized access-rules file.')
                            rules.parse(data.decode('utf-8', errors='replace').splitlines())
                        else:
                            rules.parse([])
                        rule_cache[origin] = rules
                    if not rule_cache[origin].can_fetch('RoadieArticleImporter', target):
                        raise CaptureError('robots_denied', 'This website disallows automated capture. Upload a PDF saved from your browser.')
                check_access(url)
                response = page.goto(url, wait_until='domcontentloaded', timeout=remaining_ms(deadline))
                if response is None or response.status >= 400:
                    status = response.status if response else 0
                    raise CaptureError('http_error', f'The website returned HTTP {status}. Open it in your browser or upload a saved PDF.',
                                       status == 429 or status >= 500)
                final_url = public_url(page.url, keep_fragment=True)
                check_access(final_url)
                page.wait_for_function("document.body && document.body.innerText.trim().length >= 80",
                                       timeout=remaining_ms(deadline, 20000))
                try:
                    page.wait_for_function('!document.fonts || document.fonts.status === "loaded"',
                                           timeout=remaining_ms(deadline, 8000))
                except BrowserTimeout:
                    warnings.append('Some fonts did not finish loading. Check the PDF layout.')
                height, position = 0, 0
                for _ in range(30):
                    height = page.evaluate('document.documentElement.scrollHeight')
                    if height > 60000:
                        raise CaptureError('page_too_long', 'This page exceeds the capture length limit. Save a shorter PDF in your browser.')
                    if position >= height:
                        break
                    page.evaluate('(y) => window.scrollTo(0, y)', position)
                    page.wait_for_timeout(min(200, remaining_ms(deadline)))
                    position += 850
                else:
                    if position < height:
                        raise CaptureError('page_too_long', 'This page keeps loading more content. Save the required section as a PDF.')
                page.evaluate('window.scrollTo(0, 0)')
                try:
                    page.wait_for_function('Array.from(document.images).every(i => i.complete)',
                                           timeout=remaining_ms(deadline, 10000))
                except BrowserTimeout:
                    warnings.append('Some images did not finish loading. Review illustrations in the PDF.')
                if page.evaluate('Array.from(document.images).some(i => !i.complete || !i.naturalWidth)'):
                    warnings.append('One or more images could not be loaded. Check illustrations before publication.')
                title = page.title()
                if not title and page.locator('h1').count():
                    title = page.locator('h1').first.text_content()
                title = (title or 'Website PDF').strip()[:300]
                visible_text = page.locator('body').inner_text(timeout=remaining_ms(deadline))
                low = visible_text.lower()
                if any(term in low[:2500] for term in ('verify you are human', 'checking your browser',
                        'access denied', 'just a moment...', 'enable javascript and cookies to continue')):
                    raise CaptureError('challenge', 'The website presented a browser challenge. Upload a PDF saved from your browser.')
                if page.locator('input[type="password"]').count() and len(visible_text) < 1500:
                    raise CaptureError('login_required', 'This page requires sign-in. Upload an authorized PDF saved from your browser.')
                final_url = public_url(page.url, keep_fragment=True)
                check_access(final_url)
                page.emulate_media(media=options.get('media', 'screen'))
                if proxy.remaining_bytes < 0:
                    raise CaptureError('download_limit', 'This page exceeds the capture download limit. Upload a PDF saved from your browser.')
                remaining_ms(deadline)
                pending = output / 'capture.tmp.pdf'
                page.pdf(path=str(pending), format='A4', print_background=True,
                    margin={'top': '12mm', 'bottom': '12mm', 'left': '10mm', 'right': '10mm'},
                    tagged=True, outline=True)
                if public_url(page.url, keep_fragment=True) != final_url:
                    raise CaptureError('navigation_changed', 'The page changed during capture. Retry this import.', True)
                count, pdf_text = validate_pdf(pending, limits['max_bytes'], limits['max_pages'])
                if len(pdf_text.strip()) < 80:
                    warnings.append('Little selectable text was found. Check the PDF preview before processing.')
                if len(visible_text) > 500 and len(pdf_text) < len(visible_text) * .45:
                    warnings.append('The PDF may omit visible page content. Compare it with the original or retry with print layout.')
                # Render the first page to verify that a nonempty PDF is visible.
                import pypdfium2 as pdfium
                with pdfium.PdfDocument(str(pending)) as pdf:
                    image = pdf[0].render(scale=.75).to_pil()
                    extrema = image.convert('L').getextrema()
                    if extrema[1] - extrema[0] < 8:
                        raise CaptureError('blank_pdf', 'The captured PDF appears blank. Try the other layout or upload a saved PDF.')
                    image.save(output / 'preview.png')
                pending.replace(output / 'capture.pdf')
                metadata = {'version': 1, 'source_kind': 'website', 'capture_method': 'browser_pdf',
                    'submitted_url': url, 'original_url': final_url, 'article_title': title,
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'renderer': 'playwright-chromium', 'renderer_version': importlib.metadata.version('playwright'),
                    'browser_version': browser.version, 'capture_options': options,
                    'pdf_sha256': sha256((output / 'capture.pdf').read_bytes()).hexdigest(),
                    'page_count': count, 'warnings': sorted(set(warnings))}
                checkpoint = output / 'capture.json.tmp'
                checkpoint.write_text(json.dumps(metadata), encoding='utf-8')
                checkpoint.replace(output / 'capture.json')
                return metadata
            finally:
                browser.close()
    except CaptureError:
        raise
    except BrowserTimeout as error:
        raise CaptureError('timeout', 'The website took too long to render. Retry or upload a PDF saved from your browser.', True) from error
    except BrowserError as error:
        message = str(error)
        if 'Executable doesn\'t exist' in message:
            raise CaptureError('browser_missing', 'Chromium is not installed. Run the website browser setup command.') from error
        if 'ERR_CERT' in message:
            raise CaptureError('certificate', 'The website’s HTTPS certificate could not be verified.') from error
        raise CaptureError('browser_error', 'The browser could not load this page. Retry or upload a saved PDF.', True) from error


def main():
    payload = json.load(sys.stdin)
    try:
        capture(payload['url'], payload['options'], payload['output'], payload['limits'])
    except CaptureError as error:
        diagnostic = ''
        if error.__cause__:
            diagnostic = re.sub(r'https?://\S+', '<website>', str(error.__cause__).splitlines()[0])[:300]
        print(json.dumps({'code': error.code, 'message': str(error), 'retryable': error.retryable, 'diagnostic': diagnostic}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({'code': 'capture_error', 'message': 'Capture failed unexpectedly. Retry or upload a saved PDF.', 'retryable': True}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
