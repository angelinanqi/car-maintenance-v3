const aiReferenceNotice =
    'AI guidance is for learning and reference and may be incomplete or incorrect. '
    'Confirm repairs and specifications with a qualified mechanic.';

class MechanicQuestion {
  final String question;
  final String reason;
  const MechanicQuestion({required this.question, required this.reason});

  factory MechanicQuestion.fromJson(Map<String, dynamic> data) =>
      MechanicQuestion(
        question: data['question'] as String,
        reason: data['reason'] as String,
      );
}

class MechanicPreparation {
  final String concernSummary;
  final String vehicleSummary;
  final List<MechanicQuestion> questions;
  final List<String> detailsToNote;
  final bool tailored;
  const MechanicPreparation({
    required this.concernSummary,
    required this.vehicleSummary,
    required this.questions,
    required this.detailsToNote,
    required this.tailored,
  });

  factory MechanicPreparation.fromJson(Map<String, dynamic> data) {
    final questions = (data['questions'] as List)
        .map(
          (row) =>
              MechanicQuestion.fromJson(Map<String, dynamic>.from(row as Map)),
        )
        .toList();
    if (questions.length < 3 || questions.length > 5) {
      throw const FormatException('Expected a short mechanic question list.');
    }
    return MechanicPreparation(
      concernSummary: data['concern_summary'] as String,
      vehicleSummary: data['vehicle_summary'] as String,
      questions: questions,
      detailsToNote: (data['details_to_note'] as List).cast<String>(),
      tailored: data['tailored'] as bool,
    );
  }

  String asText() {
    final lines = <String>[
      'Questions for a mechanic',
      vehicleSummary,
      '',
      'My concern: $concernSummary',
      '',
    ];
    for (var index = 0; index < questions.length; index++) {
      lines.add('${index + 1}. ${questions[index].question}');
      lines.add('Why ask: ${questions[index].reason}');
      lines.add('');
    }
    lines.add('Details to bring:');
    lines.addAll(detailsToNote.map((detail) => '- $detail'));
    lines.add(
      '\nDiscussion notes for a professional; no diagnosis has been confirmed.',
    );
    return lines.join('\n');
  }
}
