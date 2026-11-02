"""Link a confirmed Supabase identity to its existing administrator profile.

Run as a trusted operator: python -m scripts.link_supabase_admin AUTH_USER_UUID
No credentials, role input, invitations, or password changes are accepted.
"""
import argparse
from uuid import UUID

from backend import db


def link_admin(auth_user_id):
    user = db.client().auth.admin.get_user_by_id(str(UUID(auth_user_id))).user
    if not user.email_confirmed_at:
        raise ValueError('Confirm the Supabase account email before linking.')
    rows = db.client().table('app_users').select('id,email,auth_user_id').eq('role', 'admin').eq('email', (user.email or '').strip().lower()).execute().data
    if len(rows) != 1 or rows[0]['email'] != (user.email or '').strip().lower():
        raise ValueError('Expected one existing administrator with the same verified email.')
    profile = rows[0]
    if profile.get('auth_user_id') not in (None, user.id):
        raise ValueError('The administrator is already linked to another Auth identity.')
    result = db.client().table('app_users').update({'auth_user_id': user.id}).eq('id', profile['id'])
    if not profile.get('auth_user_id'):
        result = result.is_('auth_user_id', 'null')
    else:
        result = result.eq('auth_user_id', user.id)
    if not result.execute().data:
        raise ValueError('The profile changed. Inspect it before retrying.')
    print('Administrator linked for Supabase sign-in. Existing application ID, role and records retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('auth_user_id', type=str)
    args = parser.parse_args()
    link_admin(args.auth_user_id)
