import 'dart:io';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/accident_repository.dart';
import '../data/content_repository.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';
import 'accident_form.dart';
import 'emergency_help.dart';

class EmergencyGuidePage extends StatefulWidget {
  final EmergencyGuide guide;
  final AppState state;
  final AccidentRepository accidents;
  final ContentRepository? content;
  const EmergencyGuidePage({
    super.key,
    required this.guide,
    required this.state,
    required this.accidents,
    this.content,
  });
  @override
  State<EmergencyGuidePage> createState() => _EmergencyGuidePageState();
}

class _EmergencyGuidePageState extends State<EmergencyGuidePage> {
  late final List<bool> _checked;
  @override
  void initState() {
    super.initState();
    _checked = List.filled(widget.guide.steps.length, false);
  }

  Widget _image(EmergencyStep step) {
    const unavailable = Padding(
      padding: EdgeInsets.all(16),
      child: Text(
        'Illustration unavailable. Use the written instructions above. Download the guide again when connected.',
      ),
    );
    // The current image contract has no alt text. Do not fabricate a description.
    final image = step.localImagePath != null
        ? Image.file(
            File(step.localImagePath!),
            fit: BoxFit.contain,
            errorBuilder: (_, _, _) => unavailable,
          )
        : Image.network(
            step.imageUrl,
            fit: BoxFit.contain,
            loadingBuilder: (_, child, progress) => progress == null
                ? child
                : const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text(
                      'Loading illustration. You can continue with the written instructions.',
                    ),
                  ),
            errorBuilder: (_, _, _) => unavailable,
          );
    return Semantics(
      label: 'Supporting illustration for ${step.title}',
      image: true,
      child: ExcludeSemantics(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 360),
          child: image,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final guide = widget.guide;
    final completed = _checked.where((value) => value).length;
    return Scaffold(
      appBar: AppBar(title: Text(guide.title)),
      bottomNavigationBar: EmergencyHelpBar(
        onHelp: () => openEmergencyHelp(
          context,
          widget.state,
          widget.content ?? ContentRepository(widget.state.store),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(guide.title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          if (guide.scenarioKey == 'minor-accident') ...[
            EmergencyNotice(
              title: 'Safety before recording details',
              message:
                  'This incident flow is for minor property damage with no injuries. For injuries, fire or immediate danger, call emergency services.',
              danger: true,
              action: OutlinedButton.icon(
                onPressed: () => dialAssistance(context, '999'),
                icon: const Icon(Icons.call),
                label: const Text('Call 999'),
              ),
            ),
            const SizedBox(height: 16),
          ],
          if (!guide.available)
            const EmergencyNotice(
              title: 'Instructions unavailable',
              message:
                  'No reviewed instructions are available for this situation. You can still call for help below.',
            )
          else ...[
            if (guide.description.isNotEmpty) ...[
              Text(guide.description),
              const SizedBox(height: 16),
            ],
            if (guide.safetyWarnings.isNotEmpty) ...[
              EmergencyNotice(
                title: 'Safety warnings',
                message: guide.safetyWarnings,
                danger: true,
              ),
              const SizedBox(height: 16),
            ],
            Text('What to do', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text('$completed of ${guide.steps.length} steps marked.'),
            const Text(
              'Checks reset when you leave. They do not confirm it is safe to drive.',
            ),
            const SizedBox(height: 16),
            for (var i = 0; i < guide.steps.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Material(
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  clipBehavior: Clip.antiAlias,
                  child: ExpansionTile(
                    key: PageStorageKey('step-${guide.steps[i].id}'),
                    // Legacy descriptions can contain safety-critical material.
                    // Keep every instruction open initially; users can collapse
                    // individual explanations without following a fixed wizard.
                    initiallyExpanded: true,
                    leading: Semantics(
                      label: 'Mark step ${i + 1}: ${guide.steps[i].title}',
                      child: Checkbox(
                        value: _checked[i],
                        onChanged: (value) =>
                            setState(() => _checked[i] = value!),
                      ),
                    ),
                    title: Text('${i + 1}. ${guide.steps[i].title}'),
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Text(guide.steps[i].description),
                        ),
                      ),
                      if (guide.steps[i].localImagePath != null ||
                          guide.steps[i].imageUrl.isNotEmpty)
                        ExpansionTile(
                          key: PageStorageKey('image-${guide.steps[i].id}'),
                          initiallyExpanded: i == 0,
                          title: const Text('View illustration'),
                          children: [_image(guide.steps[i])],
                        ),
                    ],
                  ),
                ),
              ),
            ExpansionTile(
              title: const Text('Sources and review details'),
              childrenPadding: const EdgeInsets.all(16),
              expandedCrossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  guide.savedOffline
                      ? 'Available offline'
                      : 'Online guide. Save a copy from Offline guides before you need it.',
                ),
                Text(
                  guide.bundled
                      ? 'Sources checked ${guide.reviewedAt}'
                      : 'Reviewed ${guide.reviewedAt}',
                ),
                if (guide.bundled)
                  const Text(
                    'General safety guidance from the linked sources. This is not a vehicle-specific repair procedure.',
                  ),
                if (guide.legacy && !guide.bundled)
                  const Text(
                    'Legacy local copy; backend publication has not been confirmed.',
                  ),
                SelectableText('Source: ${guide.source}'),
              ],
            ),
          ],
          if (guide.scenarioKey == 'minor-accident') ...[
            const SizedBox(height: 24),
            const Text(
              'Once you can safely record information, save what you know. You can continue later.',
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => AccidentForm(
                    repository: widget.accidents,
                    onHelp: () => openEmergencyHelp(
                      context,
                      widget.state,
                      widget.content ?? ContentRepository(widget.state.store),
                    ),
                  ),
                ),
              ),
              icon: const Icon(Icons.assignment_outlined),
              label: const Text('Collect accident information'),
            ),
          ],
          const SizedBox(height: 16),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Back to scenarios'),
          ),
        ],
      ),
    );
  }
}
