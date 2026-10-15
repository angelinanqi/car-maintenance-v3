// Opt-in UI continuation of tests/verify_manual_rag.py using its actual API reply.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:car_app/app_state.dart';
import 'package:car_app/data/api_client.dart';
import 'package:car_app/data/chat_repository.dart';
import 'package:car_app/data/local_store.dart';
import 'package:car_app/screens/chat.dart';
import 'package:car_app/widgets/chat_attachment.dart';

void main() {
  const folder = String.fromEnvironment('RAG_VERIFICATION_DIR');
  testWidgets(
    'Retrieved manual media renders in the actual assistant message',
    (tester) async {
      final report =
          jsonDecode(File('$folder/report.json').readAsStringSync()) as Map;
      final replies = (report['queries'] as List)
          .where(
            (q) =>
                q['status'] == 200 &&
                (q['response']['attachments'] as List).isNotEmpty,
          )
          .toList();
      expect(
        replies,
        isNotEmpty,
        reason: 'Real retrieval must produce media before UI testing.',
      );
      tester.view.physicalSize = const Size(420, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final captureKey = GlobalKey();
      await tester.runAsync(() async {
        await (FontLoader(
          'MaterialIcons',
        )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
      });
      if (Platform.isWindows) {
        final fontBytes = File('C:/Windows/Fonts/arial.ttf').readAsBytesSync();
        await tester.runAsync(() async {
          await (FontLoader(
            'VerificationFont',
          )..addFont(Future.value(ByteData.sublistView(fontBytes)))).load();
        });
      }
      var nextReply = 0;
      final api = ApiClient(
        baseUrl: 'https://verification.example',
        client: MockClient((request) async {
          if (request.url.path == '/knowledge/scopes') {
            return http.Response(
              jsonEncode([
                {
                  'scope_type': 'category',
                  'scope_id': 'test-scope',
                  'label': 'Verified manual',
                  'available': true,
                },
              ]),
              200,
            );
          }
          if (request.url.path == '/chat') {
            final reply = replies[nextReply++]['response'];
            return http.Response(
              jsonEncode(reply),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            );
          }
          final attachments = replies.expand(
            (q) => q['response']['attachments'] as List,
          );
          final match = attachments.where(
            (a) => a['asset_endpoint'] == request.url.path,
          );
          if (match.isNotEmpty &&
              match.first['verification_asset_file'] != null) {
            return http.Response.bytes(
              File(
                '$folder/${match.first['verification_asset_file']}',
              ).readAsBytesSync(),
              200,
            );
          }
          return http.Response('Missing verification asset', 404);
        }),
      );
      final state = AppState(LocalStore())..accountId = 'verification-owner';
      addTearDown(state.dispose);
      await tester.pumpWidget(
        RepaintBoundary(
          key: captureKey,
          child: MaterialApp(
            theme: ThemeData(fontFamily: 'VerificationFont'),
            home: Chat(
              state: state,
              repository: FastApiChatRepository(api),
              contextData: const {'categoryId': 'test-scope'},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField),
        replies.first['question'] as String,
      );
      await tester.tap(find.byTooltip('Send question'));
      await tester.pumpAndSettle();
      final firstAttachments = replies.first['response']['attachments'] as List;
      expect(
        find.byType(ChatAttachment),
        findsNWidgets(firstAttachments.length),
      );
      expect(
        find
            .byType(SelectableText)
            .evaluate()
            .any(
              (e) =>
                  (e.widget as SelectableText).data ==
                  replies.first['response']['answer'],
            ),
        isTrue,
      );
      expect(tester.takeException(), isNull);

      Future<void> waitForImagePixels() async {
        for (var attempt = 0; attempt < 40; attempt++) {
          final images = find
              .byType(RawImage)
              .evaluate()
              .map((e) => e.widget as RawImage);
          if (images.isNotEmpty &&
              images.every((image) => image.image != null)) {
            return;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 50)),
          );
          await tester.pump();
        }
        fail('Real asset bytes did not produce visible decoded image pixels.');
      }

      if (firstAttachments.any((a) => a['verification_asset_file'] != null)) {
        await waitForImagePixels();
      }

      Future<void> capture(String filename) async {
        await tester.runAsync(() async {
          final boundary =
              captureKey.currentContext!.findRenderObject()
                  as RenderRepaintBoundary;
          final image = await boundary.toImage(pixelRatio: 1);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          File(
            '$folder/$filename',
          ).writeAsBytesSync(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      if (find.text('Expand table').evaluate().isNotEmpty) {
        await tester.ensureVisible(find.text('Expand table').first);
        await tester.pumpAndSettle();
        await capture('flutter-chat.png');
        await tester.tap(find.text('Expand table').first);
        await tester.pumpAndSettle();
        expect(find.byType(SourceTable), findsWidgets);
        expect(find.byType(InteractiveViewer), findsWidgets);
        await capture('flutter-expanded-table.png');
        final horizontal = find
            .descendant(
              of: find.byType(SourceTable).last,
              matching: find.byType(SingleChildScrollView),
            )
            .first;
        await tester.drag(horizontal, const Offset(-1000, 0));
        await tester.pumpAndSettle();
        await capture('flutter-expanded-table-scrolled.png');
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
      if (firstAttachments.any((a) => a['verification_asset_file'] != null)) {
        expect(find.byType(Image), findsWidgets);
        await tester.ensureVisible(find.text('Enlarge image').first);
        await tester.pumpAndSettle();
        await capture('flutter-chat-image.png');
        await tester.tap(find.text('Enlarge image').first);
        await tester.pumpAndSettle();
        await waitForImagePixels();
        expect(find.byType(InteractiveViewer), findsWidgets);
        expect(find.byType(Image), findsWidgets);
        await capture('flutter-expanded-image.png');
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
      // A second real reply must leave the first reply and its attachments intact.
      if (replies.length > 1) {
        await tester.enterText(
          find.byType(TextField),
          replies[1]['question'] as String,
        );
        await tester.tap(find.byTooltip('Send question'));
        await tester.pumpAndSettle();
        await tester.drag(find.byType(ListView).first, const Offset(0, 10000));
        await tester.pumpAndSettle();
        final messages = find
            .byType(ChatAttachment)
            .evaluate()
            .map((e) => (e.widget as ChatAttachment).attachment['element_id'])
            .toList();
        for (final attachment in firstAttachments) {
          expect(messages, contains(attachment['element_id']));
        }
      }
      expect(tester.takeException(), isNull);
    },
    skip: folder.isEmpty,
  );
}
