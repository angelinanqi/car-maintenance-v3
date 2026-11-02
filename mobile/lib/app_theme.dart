import 'app_spacing.dart';
import 'package:flutter/material.dart';

abstract final class AppColors {
  static const accent = Color(0xFFFFC21A);
  static const accentLight = Color(0xFFFFEBB0);
  static const canvas = Color(0xFFFFF8E6);
  static const ink = Color(0xFF2B2100);
  static const muted = Color(0xFF6B5A2E);
  static const border = Color(0xFFE6D6A5);
  static const pale = Color(0xFFFBEFC8);
  static const blue = Color(0xFFCFE4F7);
  static const blueSurface = Color(0xFFE3F0FB);
  static const blueInk = Color(0xFF12426E);
  static const danger = Color(0xFFB3261E);
  static const dangerSurface = Color(0xFFFDECEA);
  static const success = Color(0xFFDDEFE3);
  static const successInk = Color(0xFF185332);
}

ThemeData buildAppTheme() {
  final colors = ColorScheme.fromSeed(seedColor: AppColors.accent).copyWith(
    primary: AppColors.ink,
    onPrimary: const Color(0xFFFFE08A),
    primaryContainer: AppColors.accentLight,
    onPrimaryContainer: AppColors.ink,
    secondary: AppColors.blueInk,
    onSecondary: Colors.white,
    secondaryContainer: AppColors.blue,
    onSecondaryContainer: AppColors.blueInk,
    surface: Colors.white,
    onSurface: AppColors.ink,
    onSurfaceVariant: AppColors.muted,
    surfaceContainerLow: AppColors.canvas,
    surfaceContainer: AppColors.pale,
    outline: AppColors.muted,
    outlineVariant: AppColors.border,
    error: AppColors.danger,
    onError: Colors.white,
    errorContainer: AppColors.dangerSurface,
    onErrorContainer: AppColors.danger,
    surfaceTint: Colors.transparent,
  );
  final base = ThemeData(
    useMaterial3: true,
    fontFamily: 'Inter',
    colorScheme: colors,
  );
  final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(16));
  final fieldBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(14),
    borderSide: const BorderSide(color: AppColors.border),
  );
  final button = ButtonStyle(
    minimumSize: const WidgetStatePropertyAll(Size(48, 48)),
    padding: const WidgetStatePropertyAll(
      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
    shape: WidgetStatePropertyAll(shape),
    textStyle: const WidgetStatePropertyAll(
      TextStyle(fontFamily: 'Inter', fontSize: 15, fontWeight: FontWeight.w700),
    ),
  );
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.canvas,
    textTheme: base.textTheme.copyWith(
      headlineLarge: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 32,
        fontWeight: FontWeight.w800,
        color: AppColors.ink,
        height: 1.15,
        letterSpacing: -1,
      ),
      headlineMedium: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 28,
        fontWeight: FontWeight.w800,
        color: AppColors.ink,
        height: 1.18,
        letterSpacing: -.8,
      ),
      headlineSmall: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 24,
        fontWeight: FontWeight.w700,
        color: AppColors.ink,
        height: 1.2,
        letterSpacing: -.5,
      ),
      titleLarge: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: AppColors.ink,
      ),
      titleMedium: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 16,
        fontWeight: FontWeight.w700,
        color: AppColors.ink,
      ),
      bodyLarge: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 16,
        color: AppColors.ink,
        height: 1.5,
      ),
      bodyMedium: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 14,
        color: AppColors.ink,
        height: 1.45,
      ),
      bodySmall: const TextStyle(
        fontFamily: 'Inter',
        fontSize: 13,
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
      toolbarHeight: 72,
      titleSpacing: AppSpacing.screen,
      titleTextStyle: TextStyle(
        fontFamily: 'Inter',
        fontSize: 26,
        fontWeight: FontWeight.w800,
        color: AppColors.ink,
        letterSpacing: -.7,
      ),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: AppSpacing.standard),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.border),
      ),
      clipBehavior: Clip.antiAlias,
    ),
    filledButtonTheme: FilledButtonThemeData(style: button),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: button.copyWith(
        backgroundColor: const WidgetStatePropertyAll(AppColors.pale),
        side: const WidgetStatePropertyAll(BorderSide.none),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: button),
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        foregroundColor: AppColors.muted,
        backgroundColor: AppColors.pale,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    inputDecorationTheme: InputDecorationThemeData(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
      border: fieldBorder,
      enabledBorder: fieldBorder,
      focusedBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: AppColors.muted, width: 2),
      ),
      errorBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: AppColors.danger),
      ),
      focusedErrorBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: AppColors.danger, width: 2),
      ),
      labelStyle: const TextStyle(color: AppColors.muted),
      errorMaxLines: 3,
      helperMaxLines: 3,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      indicatorColor: Colors.transparent,
      elevation: 0,
      height: 74,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontFamily: 'Inter',
          fontSize: 11,
          fontWeight: states.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
          color: states.contains(WidgetState.selected)
              ? const Color(0xFF7A4E00)
              : AppColors.muted,
        ),
      ),
      iconTheme: const WidgetStatePropertyAll(
        IconThemeData(color: AppColors.muted, size: 25),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      iconColor: AppColors.muted,
      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    ),
    chipTheme: ChipThemeData(
      showCheckmark: false,
      labelStyle: const TextStyle(
        fontFamily: 'Inter',
        color: AppColors.ink,
        fontSize: 14,
      ),
      backgroundColor: AppColors.pale,
      selectedColor: AppColors.accent,
      side: BorderSide.none,
      shape: const StadiumBorder(),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.canvas,
      surfaceTintColor: Colors.transparent,
      shape: shape,
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.canvas,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.ink,
      shape: shape,
    ),
    dividerTheme: const DividerThemeData(color: AppColors.border, space: 24),
    expansionTileTheme: const ExpansionTileThemeData(
      shape: Border(),
      collapsedShape: Border(),
      iconColor: AppColors.muted,
    ),
  );
}
