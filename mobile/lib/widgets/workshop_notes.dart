import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

Future<void> copyWorkshopNotes(BuildContext context, String notes) async {
  try {
    await Clipboard.setData(ClipboardData(text: notes));
    if (context.mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Discussion notes copied.')));
    }
  } catch (_) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not copy. You can select and copy the text instead.',
          ),
        ),
      );
    }
  }
}

class WorkshopNotes extends StatelessWidget {
  final String notes;
  const WorkshopNotes({super.key, required this.notes});

  @override
  Widget build(BuildContext context) => Card.outlined(
    child: ExpansionTile(
      title: const Text('Your questions for the workshop'),
      subtitle: const Text('Refer to these when you call or visit.'),
      childrenPadding: const EdgeInsets.all(16),
      children: [
        SelectableText(notes),
        TextButton.icon(
          onPressed: () => copyWorkshopNotes(context, notes),
          icon: const Icon(Icons.copy),
          label: const Text('Copy discussion notes'),
        ),
      ],
    ),
  );
}
