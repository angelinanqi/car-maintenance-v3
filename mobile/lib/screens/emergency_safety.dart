import 'package:flutter/material.dart';
import '../app_spacing.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';
import '../widgets/emergency_widgets.dart';

class EmergencySafetyCheck extends StatefulWidget {
  final VoidCallback onContinue, onHelp;
  const EmergencySafetyCheck({
    super.key,
    required this.onContinue,
    required this.onHelp,
  });
  @override
  State<EmergencySafetyCheck> createState() => _EmergencySafetyCheckState();
}

class _EmergencySafetyCheckState extends State<EmergencySafetyCheck> {
  bool? _hurt, _away;

  Widget _question(
    String title,
    bool? value,
    ValueChanged<bool> select, {
    bool dangerYes = false,
  }) => SurfaceCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Row(
          children: [
            for (final answer in [true, false]) ...[
              if (!answer) const SizedBox(width: 12),
              Expanded(
                child: Semantics(
                  selected: value == answer,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(
                        color: value == answer
                            ? Colors.transparent
                            : AppColors.ink,
                        width: 1.5,
                      ),
                      backgroundColor: value == answer
                          ? (dangerYes && answer
                                ? AppColors.danger
                                : AppColors.accent)
                          : Colors.white,
                      foregroundColor: value == answer && dangerYes && answer
                          ? Colors.white
                          : AppColors.ink,
                    ),
                    onPressed: () => select(answer),
                    child: Text(answer ? 'Yes' : 'No'),
                  ),
                ),
              ),
            ],
          ],
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Safety check')),
    bottomNavigationBar: EmergencyHelpBar(
      onHelp: widget.onHelp,
      showEmergencyCall: true,
    ),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.screen),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Check your current situation before following the guide.',
          ),
          const SizedBox(height: 16),
          _question(
            'Is anyone hurt?',
            _hurt,
            (v) => setState(() => _hurt = v),
            dangerYes: true,
          ),
          const SizedBox(height: 12),
          _question(
            'Are you away from moving traffic?',
            _away,
            (v) => setState(() => _away = v),
          ),
          const SizedBox(height: 16),
          if (_hurt == true || _away == false) ...[
            EmergencyNotice(
              title: _hurt == true
                  ? 'Someone is hurt — get emergency help'
                  : 'Put safety first',
              message: _hurt == true
                  ? 'Call 999 and follow the operator’s instructions. Recording details and troubleshooting can wait.'
                  : 'Do not start roadside troubleshooting while exposed to moving traffic. If there is immediate danger, call 999.',
              danger: true,
              action: OutlinedButton.icon(
                onPressed: () => dialAssistance(context, '999'),
                icon: const Icon(Icons.call),
                label: const Text('Call 999'),
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Recheck your answers when the situation changes. Help is always available below.',
            ),
            const SizedBox(height: 12),
          ],
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.accent,
              foregroundColor: AppColors.ink,
            ),
            onPressed: _hurt == false && _away == true
                ? widget.onContinue
                : null,
            child: const Text('Continue to steps'),
          ),
        ],
      ),
    ),
  );
}
