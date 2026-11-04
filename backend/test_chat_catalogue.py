"""Catalogue previews stay scoped and separate from personal garage data."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.models import ChatRequest
from backend.companion_models import ChatSessionInput
from backend.services import chat


class CatalogueChatTests(unittest.TestCase):
    def test_mobile_session_contract_still_defaults_to_automatic(self):
        request = ChatSessionInput(session_token='x' * 32)
        self.assertIsNone(request.scope_type)
        self.assertIsNone(request.scope_id)
        with patch.object(chat.db, 'all_rows', return_value=[]), \
                patch.object(chat.db, 'insert') as insert, \
                patch.object(chat.vehicle_profiles, 'active_vehicle',
                             return_value={'id': 'personal', 'catalogue_id': 'alza'}), \
                patch.object(chat, 'enforce_automatic_vehicle'):
            chat.create_session('session', request.session_token, {'id': 'owner', 'role': 'user'})
        row = insert.call_args.args[1]
        self.assertTrue(row['automatic'])
        self.assertEqual(row['user_vehicle_id'], 'personal')

    def test_regular_user_cannot_create_catalogue_test_session(self):
        with patch.object(chat.db, 'insert') as insert:
            with self.assertRaises(HTTPException) as caught:
                chat.create_session('session', 'token', {'id': 'owner', 'role': 'user'},
                                    scope_type='vehicle', scope_id='alza')
        self.assertEqual(caught.exception.status_code, 403)
        insert.assert_not_called()

    def test_admin_can_create_catalogue_session_without_a_personal_vehicle(self):
        with patch.object(chat.scopes, 'resolve') as resolve, \
                patch.object(chat.db, 'all_rows', return_value=[]), \
                patch.object(chat.db, 'insert') as insert, \
                patch.object(chat.vehicle_profiles, 'active_vehicle') as personal:
            chat.create_session('session', 'token', {'id': 'owner', 'role': 'admin'},
                                scope_type='vehicle', scope_id='alza')
        resolve.assert_called_once_with('vehicle', 'alza')
        row = insert.call_args.args[1]
        self.assertEqual(row['vehicle_id'], 'alza')
        self.assertFalse(row['automatic'])
        self.assertNotIn('user_vehicle_id', row)
        personal.assert_not_called()

    def test_existing_session_cannot_switch_catalogue_vehicle(self):
        with patch.object(chat.scopes, 'resolve'), \
                patch.object(chat.db, 'all_rows', return_value=[{}]), \
                patch.object(chat, 'authorize_session', return_value={'vehicle_id': 'other'}):
            with self.assertRaises(HTTPException) as caught:
                chat.create_session('session', 'token', {'id': 'owner', 'role': 'admin'},
                                    scope_type='vehicle', scope_id='alza')
        self.assertEqual(caught.exception.status_code, 409)

    def test_catalogue_chat_does_not_load_admin_personal_profile(self):
        row = {'id': 'session', 'vehicle_id': 'alza', 'automatic': False}
        request = ChatRequest(message='Explain dashboard lights', session_id='session', session_token='token')
        with patch.object(chat, 'authorize_session', return_value=row), \
                patch.object(chat, 'enforce_vehicle'), \
                patch.object(chat, 'conversation_scope', return_value={}), \
                patch.object(chat, 'recent_messages', return_value=[]), \
                patch.object(chat.vehicle_profiles, 'load') as profile, \
                patch.object(chat.personal_maintenance, 'load', return_value=None):
            result = chat.load(request, {'id': 'owner', 'role': 'admin'})
        self.assertIsNone(result[4])
        self.assertIsNone(result[5])
        profile.assert_not_called()


if __name__ == '__main__':
    unittest.main()
