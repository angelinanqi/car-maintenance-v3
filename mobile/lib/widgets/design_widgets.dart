import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_theme.dart';

/// Keeps form fields mounted so validation also includes scrolled-off fields.
class FormList extends StatelessWidget {
  final EdgeInsetsGeometry padding;
  final List<Widget> children;
  const FormList({
    super.key,
    this.padding = const EdgeInsets.all(AppSpacing.screen),
    required this.children,
  });
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: padding,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

class NoteDialog extends StatefulWidget {
  const NoteDialog({super.key});
  @override
  State<NoteDialog> createState() => _NoteDialogState();
}

/// Reference fields place the label inside the outlined surface, above its value.
class ReferenceTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final String? hint, helper;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;
  final bool enabled;
  final int maxLines;
  final int? minLines, maxLength;
  const ReferenceTextField({
    super.key,
    required this.controller,
    required this.label,
    this.hint,
    this.helper,
    this.keyboardType,
    this.validator,
    this.enabled = true,
    this.maxLines = 1,
    this.minLines,
    this.maxLength,
  });
  @override
  Widget build(BuildContext context) => Semantics(
    label: label,
    child: Stack(
      children: [
        TextFormField(
          controller: controller,
          enabled: enabled,
          keyboardType: keyboardType,
          maxLines: maxLines,
          minLines: minLines,
          maxLength: maxLength,
          validator: validator,
          style: const TextStyle(
            fontFamily: 'Inter',
            color: AppColors.ink,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
          decoration: InputDecoration(
            hintText: hint,
            helperText: helper,
            counterText: '',
            contentPadding: const EdgeInsets.fromLTRB(16, 30, 16, 12),
          ),
        ),
        Positioned(
          left: 16,
          top: 10,
          child: IgnorePointer(
            child: Text(
              label,
              style: const TextStyle(color: AppColors.muted, fontSize: 13),
            ),
          ),
        ),
      ],
    ),
  );
}

class _NoteDialogState extends State<NoteDialog> {
  final _text = TextEditingController();
  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Add note'),
    content: SingleChildScrollView(
      child: TextField(
        controller: _text,
        minLines: 3,
        maxLines: 6,
        decoration: const InputDecoration(labelText: 'Your note'),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: () {
          if (_text.text.trim().isNotEmpty)
            Navigator.pop(context, _text.text.trim());
        },
        child: const Text('Save note'),
      ),
    ],
  );
}

/// MyRoadie artwork for compact placements, assistant avatars and illustrations.
enum MascotArtwork {
  logo('assets/images/branding/roadie_logo.png'),
  chatbot('assets/images/mascots/roadie_chatbot.png'),
  companion('assets/images/mascots/roadie_mascot.png');

  final String asset;
  const MascotArtwork(this.asset);
}

class Mascot extends StatelessWidget {
  final double size;
  final MascotArtwork artwork;
  const Mascot({super.key, this.size = 52, this.artwork = MascotArtwork.logo});

  @override
  Widget build(BuildContext context) => Image.asset(
    artwork.asset,
    width: size,
    height: size,
    fit: BoxFit.contain,
    semanticLabel: 'MyRoadie, your car assistant',
  );
}

class SurfaceCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color, borderColor;
  final VoidCallback? onTap;
  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.standard),
    this.color = Colors.white,
    this.borderColor = AppColors.border,
    this.onTap,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.standard),
    child: Material(
      color: color,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: borderColor),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(padding: padding, child: child),
      ),
    ),
  );
}

class StatusPill extends StatelessWidget {
  final String text;
  final Color color, foreground;
  const StatusPill(
    this.text, {
    super.key,
    this.color = AppColors.pale,
    this.foreground = AppColors.ink,
  });
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(9),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: foreground,
        fontSize: 13,
        fontWeight: FontWeight.w700,
      ),
    ),
  );
}

class ActionRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;
  const ActionRow({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.onTap,
    this.trailing,
  });
  @override
  Widget build(BuildContext context) => SurfaceCard(
    onTap: onTap,
    child: Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.accentLight,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: const Color(0xFF7A4E00)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              if (subtitle != null)
                Text(subtitle!, style: const TextStyle(color: AppColors.muted)),
            ],
          ),
        ),
        trailing ?? const Icon(Icons.chevron_right, color: AppColors.muted),
      ],
    ),
  );
}

class EmptyHistory extends StatelessWidget {
  final VoidCallback onAdd;
  const EmptyHistory({super.key, required this.onAdd});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(
      top: AppSpacing.large,
      bottom: AppSpacing.section,
    ),
    child: Column(
      children: [
        const Mascot(size: 160, artwork: MascotArtwork.companion),
        const SizedBox(height: 18),
        Text(
          'No services recorded yet',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const Text(
          'Add your first service and we’ll start tracking what’s due next.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.muted),
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: onAdd,
            child: const Text('Add first record'),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'Or ask your workshop to record it for you',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.muted),
        ),
      ],
    ),
  );
}

class HomeSkeleton extends StatelessWidget {
  const HomeSkeleton({super.key});
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.screen),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 130,
                height: 36,
                decoration: BoxDecoration(
                  color: const Color(0xFFF0E3BC),
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
              const Spacer(),
              const CircleAvatar(
                radius: 22,
                backgroundColor: Color(0xFFF0E3BC),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.standard),
          Align(
            alignment: Alignment.centerLeft,
            child: Container(
              width: 210,
              height: 24,
              decoration: BoxDecoration(
                color: const Color(0xFFF0E3BC),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.standard),
          for (final height in [70.0, 190.0, 70.0, 110.0])
            Container(
              height: height,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: const Color(0xFFF0E3BC),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
        ],
      ),
    ),
  );
}
