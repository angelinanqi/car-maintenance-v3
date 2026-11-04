/// Position only existing authorised originals; old replies retain their layout.
class ChatAnswerSection {
  final String text;
  final List<Map<String, dynamic>> attachments;
  const ChatAnswerSection(this.text, this.attachments);
}

class ChatAnswerLayout {
  final List<ChatAnswerSection> sections;
  final List<Map<String, dynamic>> remainingAttachments;
  const ChatAnswerLayout(this.sections, this.remainingAttachments);
}

ChatAnswerLayout chatLayout(
  String answer,
  List<Map<String, dynamic>> sections,
  List<Map<String, dynamic>> attachments,
) {
  if (sections.isEmpty || sections.length > 16 ||
      sections.any((section) => section['text'] is! String ||
          (section['text'] as String).trim().isEmpty) ||
      sections.map((section) => section['text'] as String).join('\n\n') != answer) {
    return ChatAnswerLayout(const [], attachments);
  }
  final available = <String, Map<String, dynamic>>{
    for (final attachment in attachments)
      if (attachment['reference_label'] is String)
        attachment['reference_label'] as String: attachment,
  };
  final used = <String>{};
  final placed = <ChatAnswerSection>[];
  for (final section in sections) {
    final raw = section['reference_labels'];
    final labels = raw is List ? raw.take(5) : const [];
    final selected = <Map<String, dynamic>>[];
    for (final label in labels) {
      if (label is String && RegExp(r'^V[1-9]\d*$').hasMatch(label) &&
          available.containsKey(label) && used.add(label)) {
        selected.add(available[label]!);
      }
    }
    placed.add(ChatAnswerSection(section['text'] as String, selected));
  }
  return ChatAnswerLayout(placed,
      attachments.where((item) => !used.contains(item['reference_label'])).toList());
}
