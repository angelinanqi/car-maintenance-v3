import 'package:flutter/material.dart';

const double pillNavHeight = 64;
const double pillNavItemWidth = 59;
const double pillNavLongLabelWidth = 76;
const double pillNavItemHeight = 48;
const double pillNavHorizontalPadding = 8;
const double pillNavSideMargin = 16;
const double pillNavBottomMargin = 12;
const double pillNavIndicatorWidth = 48;
const double pillNavIndicatorHeight = 28;
const double pillNavIconSize = 24;
const double pillNavIconLabelGap = 4;
const double pillNavLabelFontSize = 11;
const Duration pillNavIndicatorDuration = Duration(milliseconds: 180);

class PillNavDestination {
  final IconData icon;
  final String label;
  final double itemWidth;

  const PillNavDestination({
    required this.icon,
    required this.label,
    this.itemWidth = pillNavItemWidth,
  });
}

class PillNavBar extends StatelessWidget {
  final List<PillNavDestination> destinations;
  final int selectedIndex;
  final ValueChanged<int> onTap;

  const PillNavBar({
    super.key,
    required this.destinations,
    required this.selectedIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return SafeArea(
      top: false,
      minimum: const EdgeInsets.fromLTRB(
        pillNavSideMargin,
        0,
        pillNavSideMargin,
        pillNavBottomMargin,
      ),
      child: Center(
        heightFactor: 1,
        child: SizedBox(
          height: pillNavHeight,
          child: DecoratedBox(
            decoration: ShapeDecoration(
              color: colors.surfaceContainer,
              shape: StadiumBorder(
                side: BorderSide(color: colors.outlineVariant, width: 0.75),
              ),
              shadows: [
                BoxShadow(
                  color: colors.shadow.withValues(alpha: 0.2),
                  blurRadius: 6,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Material(
              type: MaterialType.transparency,
              surfaceTintColor: Colors.transparent,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: pillNavHorizontalPadding,
                ),
                child: MediaQuery.withClampedTextScaling(
                  maxScaleFactor: 1.2,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (var index = 0; index < destinations.length; index++)
                        _PillNavItem(
                          destination: destinations[index],
                          selected: index == selectedIndex,
                          onTap: () => onTap(index),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PillNavItem extends StatelessWidget {
  final PillNavDestination destination;
  final bool selected;
  final VoidCallback onTap;

  const _PillNavItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final itemColor = selected
        ? colors.onPrimaryContainer
        : colors.onSurfaceVariant;

    return Semantics(
      button: true,
      selected: selected,
      label: destination.label,
      child: ExcludeSemantics(
        child: SizedBox(
          width: destination.itemWidth,
          height: pillNavItemHeight,
          child: InkWell(
            onTap: onTap,
            customBorder: const StadiumBorder(),
            splashFactory: NoSplash.splashFactory,
            overlayColor: const WidgetStatePropertyAll(Colors.transparent),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                AnimatedContainer(
                  duration: pillNavIndicatorDuration,
                  curve: Curves.easeInOut,
                  width: pillNavIndicatorWidth,
                  height: pillNavIndicatorHeight,
                  decoration: ShapeDecoration(
                    color: selected
                        ? colors.primaryContainer
                        : Colors.transparent,
                    shape: const StadiumBorder(),
                  ),
                  child: Icon(
                    destination.icon,
                    size: pillNavIconSize,
                    color: itemColor,
                  ),
                ),
                const SizedBox(height: pillNavIconLabelGap),
                Text(
                  destination.label,
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: itemColor,
                    fontSize: pillNavLabelFontSize,
                    height: 1,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
