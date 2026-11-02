import '../app_spacing.dart';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/accident_repository.dart';
import '../data/content_repository.dart';
import '../data/local_store.dart';
import '../data/api_client.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';
import 'accident_reports.dart';
import 'emergency_help.dart';
import 'accident_form.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';

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
  final _images = <String, Future<Uint8List>>{};
  @override
  void initState() {
    super.initState();
    _checked = List.filled(widget.guide.steps.length, false);
  }

  Future<Uint8List> _readImage(EmergencyStep step) async {
    Uint8List bytes;
    if (step.localImagePath != null) {
      final file = File(step.localImagePath!);
      if (await file.length() > LocalStore.maxPhotoBytes)
        throw const FormatException('Image too large');
      bytes = await file.readAsBytes();
    } else {
      final api = widget.content?.api;
      if (api == null) throw const ApiException('Image unavailable');
      bytes = await api.imageBytes(step.imageUrl);
    }
    await LocalStore.validateImage(bytes);
    return bytes;
  }

  Widget _image(EmergencyStep step) {
    const unavailable = Padding(
      padding: EdgeInsets.all(16),
      child: Text(
        'Illustration unavailable. Use the written instructions above. Download the guide again when connected.',
      ),
    );
    // The current image contract has no alt text. Do not fabricate a description.
    final image = FutureBuilder<Uint8List>(
      future: _images.putIfAbsent(
        step.localImagePath ?? step.imageUrl,
        () => _readImage(step),
      ),
      builder: (_, snapshot) {
        if (snapshot.hasError) return unavailable;
        if (!snapshot.hasData)
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Loading illustration. You can continue with the written instructions.',
            ),
          );
        return Image.memory(
          snapshot.data!,
          fit: BoxFit.contain,
          errorBuilder: (_, _, _) => unavailable,
        );
      },
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
      appBar: AppBar(
        title: Text(guide.title),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 20),
            child: Center(
              child: StatusPill(
                guide.savedOffline ? 'Offline' : 'Online',
                color: AppColors.success,
                foreground: AppColors.successInk,
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.screen),
          child: Row(
            children: [
              Expanded(
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.danger,
                    foregroundColor: Colors.white,
                  ),
                  onPressed: () => openEmergencyHelp(
                    context,
                    widget.state,
                    widget.content ?? ContentRepository(widget.state.store),
                  ),
                  child: const Text('Call roadside'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AccidentForm(
                        repository: widget.accidents,
                        incidentType: guide.title,
                        onHelp: () => openEmergencyHelp(
                          context,
                          widget.state,
                          widget.content ??
                              ContentRepository(widget.state.store),
                        ),
                      ),
                    ),
                  ),
                  child: const Text('Save incident'),
                ),
              ),
            ],
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: [
          Text(
            'Tap a step to open or close it',
            style: Theme.of(
              context,
            ).textTheme.bodyLarge?.copyWith(color: AppColors.muted),
          ),
          const SizedBox(height: 16),
          if (guide.isAccident) ...[
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
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                    side: const BorderSide(color: AppColors.border),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: ExpansionTile(
                    key: PageStorageKey('step-${guide.steps[i].id}'),
                    initiallyExpanded: i == 0,
                    leading: CircleAvatar(
                      backgroundColor: i == 0
                          ? AppColors.accent
                          : AppColors.pale,
                      foregroundColor: AppColors.ink,
                      radius: 15,
                      child: Text('${i + 1}'),
                    ),
                    title: Text(
                      guide.steps[i].title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Text(guide.steps[i].description),
                        ),
                      ),
                      CheckboxListTile(
                        title: const Text('Mark this step'),
                        value: _checked[i],
                        onChanged: (value) =>
                            setState(() => _checked[i] = value!),
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
          if (guide.isAccident) ...[
            const SizedBox(height: 24),
            const Text(
              'Once you can safely record information, save what you know. You can continue later.',
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => AccidentReports(
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
              label: const Text('Accident forms and saved drafts'),
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
