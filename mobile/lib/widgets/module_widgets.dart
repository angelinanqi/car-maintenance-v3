import '../app_spacing.dart';
import 'package:flutter/material.dart';

/// Shared feedback for the learning and maintenance flows.
class ModuleMessage extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final Widget? action;
  const ModuleMessage({
    super.key,
    this.icon = Icons.info_outline,
    required this.title,
    required this.message,
    this.action,
  });

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary, size: 28),
        const SizedBox(height: 12),
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(message),
        if (action != null) ...[const SizedBox(height: 16), action!],
      ],
    ),
  );
}

class ModuleSection extends StatelessWidget {
  final String title;
  final String? description;
  const ModuleSection({super.key, required this.title, this.description});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 24, bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        if (description != null) ...[
          const SizedBox(height: 4),
          Text(description!, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ],
    ),
  );
}

/// Uses a full screen on phones so fields remain reachable above the keyboard.
class MaintenanceForm extends StatelessWidget {
  final String title;
  final bool busy;
  final VoidCallback onSave;
  final String saveLabel;
  final Widget child;
  const MaintenanceForm({
    super.key,
    required this.title,
    required this.busy,
    required this.onSave,
    required this.saveLabel,
    required this.child,
  });

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: Dialog.fullscreen(
      child: Scaffold(
        appBar: AppBar(
          automaticallyImplyLeading: false,
          leading: IconButton(
            tooltip: 'Cancel',
            onPressed: busy ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
          title: Text(title),
        ),
        body: SafeArea(
          top: false,
          child: Column(
            children: [
              if (busy) const LinearProgressIndicator(),
              Expanded(
                child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: const EdgeInsets.all(AppSpacing.screen),
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 600),
                      child: child,
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screen,
                  12,
                  AppSpacing.screen,
                  16,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        onPressed: busy ? null : () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: busy ? null : onSave,
                        child: Text(busy ? 'Saving…' : saveLabel),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
