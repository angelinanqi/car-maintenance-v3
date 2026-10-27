import 'package:flutter/material.dart';

// Warm cream surfaces; golden yellow identifies actions, red identifies danger.
abstract final class AppColors {
  static const accent = Color(0xFFF2BD42);
  static const accentLight = Color(0xFFFFEDBA);
  static const canvas = Color(0xFFFFFBF2);
  static const ink = Color(0xFF302719);
  static const muted = Color(0xFF6D604B);
  static const border = Color(0xFFE9DFC9);
}

ThemeData buildAppTheme() {
  final colors =
      ColorScheme.fromSeed(
        seedColor: AppColors.accent,
        brightness: Brightness.light,
      ).copyWith(
        primary: AppColors.accent,
        onPrimary: AppColors.ink,
        primaryContainer: AppColors.accentLight,
        onPrimaryContainer: AppColors.ink,
        secondary: AppColors.muted,
        onSecondary: Colors.white,
        secondaryContainer: const Color(0xFFF3EAD7),
        onSecondaryContainer: AppColors.ink,
        surface: Colors.white,
        onSurface: AppColors.ink,
        onSurfaceVariant: AppColors.muted,
        surfaceContainerLowest: Colors.white,
        surfaceContainerLow: AppColors.canvas,
        surfaceContainer: const Color(0xFFF8F1E2),
        surfaceContainerHigh: const Color(0xFFF1E7D2),
        surfaceContainerHighest: const Color(0xFFEADFCA),
        outline: const Color(0xFF8A795D),
        outlineVariant: AppColors.border,
        error: const Color(0xFFB3261E),
        onError: Colors.white,
        errorContainer: const Color(0xFFFCEAE8),
        onErrorContainer: const Color(0xFF7D211B),
        surfaceTint: Colors.transparent,
      );
  final base = ThemeData(useMaterial3: true, colorScheme: colors);
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(16));
  final fieldBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: BorderSide.none,
  );
  final buttonStyle = ButtonStyle(
    foregroundColor: WidgetStateProperty.resolveWith(
      (states) => states.contains(WidgetState.disabled) ? null : AppColors.ink,
    ),
    minimumSize: const WidgetStatePropertyAll(Size(48, 48)),
    padding: const WidgetStatePropertyAll(
      EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    ),
    shape: WidgetStatePropertyAll(shape),
    textStyle: const WidgetStatePropertyAll(
      TextStyle(
        fontFamily: 'Roboto',
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.canvas,
    textTheme: base.textTheme.copyWith(
      headlineSmall: base.textTheme.headlineSmall?.copyWith(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.7,
        height: 1.15,
      ),
      titleLarge: base.textTheme.titleLarge?.copyWith(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.3,
      ),
      titleMedium: base.textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w600,
      ),
      bodyLarge: base.textTheme.bodyLarge?.copyWith(height: 1.45),
      bodyMedium: base.textTheme.bodyMedium?.copyWith(height: 1.45),
      bodySmall: base.textTheme.bodySmall?.copyWith(
        color: AppColors.muted,
        height: 1.4,
      ),
    ),
    appBarTheme: const AppBarThemeData(
      backgroundColor: AppColors.canvas,
      foregroundColor: AppColors.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: 'Roboto',
        color: AppColors.ink,
        fontSize: 22,
        fontWeight: FontWeight.w700,
      ),
    ),
    cardTheme: CardThemeData(
      color: colors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: shape,
      clipBehavior: Clip.antiAlias,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: buttonStyle.copyWith(
        backgroundColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.disabled) ? null : AppColors.accent,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (states) =>
              states.contains(WidgetState.disabled) ? null : AppColors.ink,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(style: buttonStyle),
    textButtonTheme: TextButtonThemeData(style: buttonStyle),
    inputDecorationTheme: InputDecorationThemeData(
      filled: true,
      fillColor: colors.surfaceContainer,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: fieldBorder,
      enabledBorder: fieldBorder,
      focusedBorder: fieldBorder.copyWith(
        borderSide: BorderSide(color: colors.primary, width: 2),
      ),
      errorBorder: fieldBorder.copyWith(
        borderSide: BorderSide(color: colors.error),
      ),
      focusedErrorBorder: fieldBorder.copyWith(
        borderSide: BorderSide(color: colors.error, width: 2),
      ),
      helperMaxLines: 3,
      errorMaxLines: 3,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      indicatorColor: colors.primaryContainer,
      height: 72,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 12,
          fontWeight: states.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
          color: states.contains(WidgetState.selected)
              ? colors.onSurface
              : colors.onSurfaceVariant,
        ),
      ),
    ),
    listTileTheme: ListTileThemeData(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      iconColor: colors.onSurfaceVariant,
      selectedColor: colors.primary,
      selectedTileColor: colors.primaryContainer,
    ),
    chipTheme: ChipThemeData(
      backgroundColor: colors.surface,
      selectedColor: colors.primaryContainer,
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      shape: shape,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.ink,
      shape: shape,
    ),
    dividerTheme: DividerThemeData(color: colors.outlineVariant, space: 24),
    expansionTileTheme: const ExpansionTileThemeData(
      shape: Border(),
      collapsedShape: Border(),
    ),
  );
}
