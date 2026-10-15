import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:car_app/data/api_client.dart';
import 'package:car_app/models/chat_message.dart';
import 'package:car_app/widgets/chat_attachment.dart';

void main() {
  const table =
      '<table><tr><th rowspan="2">Variant</th><th colspan="2">Pressure</th></tr><tr><th>Front</th><th>Rear</th></tr><tr><td>1.3</td><td>● 210 kPa</td><td>○ 200 kPa</td></tr></table>';
  test('Text-only API responses remain compatible', () {
    expect(ChatReply.fromJson({'answer': 'Text only'}).attachments, isEmpty);
    expect(
      ChatReply.fromJson({
        'answer': 'Sources',
        'attachments': [
          {'kind': 'image'},
          {'kind': 'table'},
        ],
      }).attachments.length,
      2,
    );
  });

  testWidgets('Complete merged source table renders symbols and expands', (
    tester,
  ) async {
    final api = ApiClient(baseUrl: 'https://api.example');
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatAttachment(
            api: api,
            attachment: {
              'kind': 'table',
              'caption': 'Tyre pressure',
              'structure_valid': true,
              'html': table,
              'pages': [5],
              'notes': ['Legend: document-specific symbols'],
            },
          ),
        ),
      ),
    );
    expect(find.text('● 210 kPa'), findsOneWidget);
    expect(find.text('○ 200 kPa'), findsOneWidget);
    expect(find.text('Legend: document-specific symbols'), findsOneWidget);
    await tester.tap(find.text('Expand table'));
    await tester.pumpAndSettle();
    expect(find.byType(InteractiveViewer), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Authenticated inline images load and enlarge', (tester) async {
    final bytes = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
    );
    final api = ApiClient(
      baseUrl: 'https://api.example',
      client: MockClient((request) async {
        expect(request.url.host, 'api.example');
        expect(request.headers['Authorization'], 'Bearer account-token');
        return http.Response.bytes(bytes, 200);
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatAttachment(
            api: api,
            token: 'account-token',
            attachment: {
              'kind': 'image',
              'caption': 'Fuse diagram',
              'asset_endpoint': '/chat/sessions/session/sources/image/image',
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byType(Image), findsOneWidget);
    await tester.tap(find.text('Enlarge image'));
    await tester.pumpAndSettle();
    expect(find.byType(InteractiveViewer), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Missing image shows retry without losing the message', (
    tester,
  ) async {
    final api = ApiClient(
      baseUrl: 'https://api.example',
      client: MockClient((request) async => http.Response('missing', 404)),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatAttachment(
            api: api,
            attachment: {
              'kind': 'image',
              'asset_endpoint': '/chat/sessions/session/image',
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Retry image'), findsOneWidget);
    expect(find.textContaining('Image unavailable'), findsOneWidget);
  });

  testWidgets('Malformed table offers source fallback', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ChatAttachment(
            api: ApiClient(baseUrl: 'https://api.example'),
            attachment: {
              'kind': 'table',
              'structure_valid': false,
              'html': table,
            },
          ),
        ),
      ),
    );
    expect(find.byType(SourceTable), findsNothing);
    expect(find.textContaining('layout is unreliable'), findsOneWidget);
    expect(find.text('Open original source'), findsOneWidget);
  });

  testWidgets(
    'Missing table crop retains HTML without an unused asset request',
    (tester) async {
      final api = ApiClient(
        baseUrl: 'https://api.example',
        client: MockClient((request) async {
          fail('A known missing table crop must not be downloaded.');
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatAttachment(
              api: api,
              attachment: {
                'kind': 'table',
                'structure_valid': true,
                'html': table,
                'asset_available': false,
                'asset_endpoint': '/chat/sessions/session/table/image',
              },
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(SourceTable), findsOneWidget);
      expect(find.text('Expand table'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('One assistant message supports multiple images and a table', (
    tester,
  ) async {
    final bytes = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
    );
    final api = ApiClient(
      baseUrl: 'https://api.example',
      client: MockClient((_) async => http.Response.bytes(bytes, 200)),
    );
    final attachments = [
      {
        'kind': 'image',
        'caption': 'First diagram',
        'asset_endpoint': '/chat/sessions/session/first/image',
      },
      {
        'kind': 'image',
        'caption': 'Second diagram',
        'asset_endpoint': '/chat/sessions/session/second/image',
      },
      {
        'kind': 'table',
        'caption': 'Source schedule',
        'structure_valid': true,
        'html': table,
      },
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: [
                const Text('Assistant answer'),
                for (final attachment in attachments)
                  ChatAttachment(api: api, attachment: attachment),
              ],
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byType(Image), findsNWidgets(2));
    expect(find.byType(SourceTable), findsOneWidget);
    expect(find.text('Assistant answer'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
