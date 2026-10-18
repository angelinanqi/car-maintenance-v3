import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/chat_repository.dart';
import '../models/chat_message.dart';
import 'chat_attachment.dart';

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
    if (source['page'] != null) 'Page: ${source['page']}',
  ].join('\n');
}

/// Assistant answers use the reading width; only the user's words use a bubble.
class ChatMessageView extends StatelessWidget {
  final ChatMessage message;
  final ChatRepository repository;
  final VoidCallback? onEmergency;
  final VoidCallback? onMaintenance;
  const ChatMessageView({
    super.key,
    required this.message,
    required this.repository,
    this.onEmergency,
    this.onMaintenance,
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
        padding: const EdgeInsets.only(left: 28, top: 12, bottom: 12),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: theme.colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(12),
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
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: Text('Car Assistant', style: theme.textTheme.titleSmall),
          ),
          const SizedBox(height: 10),
          // Preserve all paragraphs, numbered steps and citation markers verbatim.
          SelectableText(
            message.text,
            style: theme.textTheme.bodyLarge?.copyWith(height: 1.6),
          ),
          if (reply?.route == 'emergency' && onEmergency != null) ...[
            const SizedBox(height: 16),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: theme.colorScheme.error,
                foregroundColor: theme.colorScheme.onError,
              ),
              onPressed: onEmergency,
              icon: const Icon(Icons.emergency_outlined),
              label: const Text('Open emergency help'),
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
          if (reply?.manualRelevant == true)
            const _ReplyNote('Relevant manual information was found.'),
          if ([
            'generation_error',
            'retrieval_error',
          ].contains(reply?.responseType))
            const _ReplyNote(
              'The AI service could not complete this answer. Try again shortly.',
            ),
          if (sources.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.only(top: 16),
              decoration: BoxDecoration(
                border: Border(
                  top: BorderSide(color: theme.colorScheme.outlineVariant),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Supporting sources (${sources.length})',
                    style: theme.textTheme.titleSmall,
                  ),
                  for (final source in sources) ...[
                    const SizedBox(height: 12),
                    SelectableText(
                      sourceDescription(source),
                      style: theme.textTheme.bodyMedium,
                    ),
                  ],
                  if (onMaintenance != null &&
                      sources.any((s) => s['source_type'] == 'personal_maintenance')) ...[
                    const SizedBox(height: 8),
                    TextButton.icon(
                      onPressed: onMaintenance,
                      icon: const Icon(Icons.receipt_long_outlined, size: 20),
                      label: const Text('View maintenance'),
                    ),
                  ],
                ],
              ),
            ),
          ],
          for (final video in reply?.videos ?? <Map<String, dynamic>>[])
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => _video(context, video),
                icon: const Icon(Icons.play_circle_outline),
                label: Text(video['title'] as String? ?? 'Open video'),
              ),
            ),
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
