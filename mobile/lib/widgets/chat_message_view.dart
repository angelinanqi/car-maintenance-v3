import 'package:flutter/material.dart';
import '../app_theme.dart';
import 'design_widgets.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/chat_repository.dart';
import '../models/chat_message.dart';
import 'chat_attachment.dart';
import 'chat_answer.dart';
import 'manual_source_link.dart';
import 'chat_video_preview.dart';

String sourceDescription(Map<String, dynamic> source) {
  final kind = switch (source['source_type']) {
    'learning_guide' => 'Learning guide',
    'emergency_protocol' => 'Reviewed emergency protocol',
    'personal_vehicle_profile' => 'Your saved vehicle details',
    'personal_maintenance' => 'Your saved services and calculated due status',
    _ => 'Reference document',
  };
  final title =
      source['title'] ??
      source['document_title'] ??
      source['document_id'] ??
      'Reference';
  final reference = source['source_reference'] as String?;
  return [
    '${source['label'] ?? 'Source'}: $kind — $title',
    if (source['reviewed_at'] != null) 'Reviewed: ${source['reviewed_at']}',
    if (reference != null && reference.isNotEmpty)
      'Source reference: $reference',
    if (source['as_of'] != null) 'As of: ${source['as_of']}',
    if (source['source_kind'] == 'website') 'Website article snapshot',
    if (source['original_url'] != null) 'Original URL: ${source['original_url']}',
    if (source['retrieved_at'] != null) 'Retrieved: ${source['retrieved_at']}',
    if (source['page'] != null) 'Page: ${source['page']}',
    if ((source['section_path'] as List? ?? []).isNotEmpty)
      'Section: ${(source['section_path'] as List).join(' → ')}',
  ].join('\n');
}

/// Assistant answers use the reading width; only the user's words use a bubble.
class ChatMessageView extends StatelessWidget {
  final ChatMessage message;
  final ChatRepository repository;
  final VoidCallback? onEmergency;
  final VoidCallback? onMaintenance;
  final ValueChanged<String>? onGuide;
  const ChatMessageView({
    super.key,
    required this.message,
    required this.repository,
    this.onEmergency,
    this.onMaintenance,
    this.onGuide,
  });

  Future<void> _video(BuildContext context, Map<String, dynamic> video) async {
    final uri = Uri.tryParse(video['url'] as String? ?? '');
    if (uri == null ||
        !['https', 'http'].contains(uri.scheme) ||
        uri.host.isEmpty) {
      return;
    }
    final stamp = (video['timestamp'] as num? ?? 0).toInt();
    try {
      if (!await launchUrl(
        uri.replace(
          queryParameters: {...uri.queryParameters, 't': '${stamp}s'},
        ),
        mode: LaunchMode.externalApplication,
      )) {
        throw StateError('No video handler');
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open the video link.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final reply = message.reply;
    if (message.isUser) {
      return Padding(
        padding: EdgeInsets.only(
          left: MediaQuery.sizeOf(context).width * 0.2,
          top: 12,
          bottom: 12,
        ),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.accent,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.circular(20),
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Semantics(
              label: 'You',
              child: SelectableText(
                message.text,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onPrimaryContainer,
                ),
              ),
            ),
          ),
        ),
      );
    }
    final sources = reply?.sources ?? [];
    return Container(
      margin: const EdgeInsets.only(left: 32, top: 8, bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.blueSurface,
        border: Border.all(color: const Color(0xFFB9D6EE)),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(20),
          bottomRight: Radius.circular(20),
          bottomLeft: Radius.circular(4),
        ),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: const Align(
              alignment: Alignment.centerLeft,
              child: Mascot(size: 30, artwork: MascotArtwork.chatbot),
            ),
          ),
          const SizedBox(height: 10),
          ChatAnswer(text: message.text),
          if (onEmergency != null && (reply?.route == 'emergency' ||
              sources.any((source) => source['source_type'] == 'emergency_protocol'))) ...[
            const SizedBox(height: 16),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: reply?.route == 'emergency'
                    ? theme.colorScheme.error : theme.colorScheme.primary,
                foregroundColor: reply?.route == 'emergency'
                    ? theme.colorScheme.onError : theme.colorScheme.onPrimary,
              ),
              onPressed: onEmergency,
              icon: const Icon(Icons.emergency_outlined),
              label: Text(reply?.route == 'emergency'
                  ? 'Open emergency help' : 'Explore emergency guidance'),
            ),
          ],
          if (onGuide != null && reply?.recommendedGuides.isNotEmpty == true) ...[
            const SizedBox(height: 16),
            const Text('Further learning'),
            for (final guide in reply!.recommendedGuides)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => onGuide!(guide['source_id'] as String),
                  icon: const Icon(Icons.menu_book_outlined),
                  label: Text('Open guide: ${guide['title']}'),
                ),
              ),
          ],
          if (repository is FastApiChatRepository)
            for (final attachment
                in reply?.attachments ?? <Map<String, dynamic>>[])
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: ChatAttachment(
                  key: ValueKey(
                    '${attachment['document_id']}:${attachment['source_revision']}:${attachment['element_id']}',
                  ),
                  attachment: attachment,
                  api: (repository as FastApiChatRepository).api,
                  token: (repository as FastApiChatRepository).account?.token,
                ),
              ),
          if (reply?.externalWarning == true)
            const _ReplyNote(
              'This answer includes information outside the available manuals.',
            ),
          if ([
            'generation_error',
            'retrieval_error',
          ].contains(reply?.responseType))
            const _ReplyNote(
              'The AI service could not complete this answer. Try again shortly.',
            ),
          if (sources.isNotEmpty) ...[
            const SizedBox(height: 16),
            Material(
              color: theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                tilePadding: const EdgeInsets.symmetric(horizontal: 16),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                leading: const Icon(Icons.library_books_outlined, size: 20),
                title: Text(
                  'Supporting sources (${sources.length})',
                  style: theme.textTheme.titleSmall,
                ),
                children: [
                  for (final source in sources) ...[
                    const SizedBox(height: 12),
                    SelectableText(
                      sourceDescription(source),
                      style: theme.textTheme.bodyMedium,
                    ),
                    if (source['source_type'] == 'manual' &&
                        source['source_endpoint'] is String &&
                        repository is FastApiChatRepository)
                      ManualSourceLink(
                        endpoint: source['source_endpoint'] as String,
                        api: (repository as FastApiChatRepository).api,
                        token: (repository as FastApiChatRepository)
                            .account
                            ?.token,
                      ),
                  ],
                ],
              ),
            ),
          ],
          if (onMaintenance != null &&
              sources.any((s) => s['source_type'] == 'personal_maintenance'))
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onMaintenance,
                icon: const Icon(Icons.receipt_long_outlined, size: 20),
                label: const Text('View maintenance'),
              ),
            ),
          if (reply?.manualLinks.isNotEmpty == true) ...[
            const SizedBox(height: 16),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text(
                'Manuals to browse',
                style: theme.textTheme.titleSmall,
              ),
              children: [
                const Text(
                  'You can inspect these manuals from your selected scope. They are not confirmed evidence for this answer.',
                ),
                for (final manual in reply!.manualLinks) ...[
                  const SizedBox(height: 12),
                  Text(manual['document_title'] as String? ?? 'Manual'),
                  if (repository is FastApiChatRepository &&
                      manual['source_endpoint'] is String)
                    ManualSourceLink(
                      endpoint: manual['source_endpoint'] as String,
                      api: (repository as FastApiChatRepository).api,
                      token:
                          (repository as FastApiChatRepository).account?.token,
                    ),
                ],
              ],
            ),
          ],
          for (final video in reply?.videos ?? <Map<String, dynamic>>[])
            ChatVideoPreview(video: video, onTap: () => _video(context, video)),
        ],
      ),
    );
  }
}

class _ReplyNote extends StatelessWidget {
  final String text;
  const _ReplyNote(this.text);
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 12),
    child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
  );
}
