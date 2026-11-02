/// Fixed Flutter logical pixels. System and keyboard insets are handled separately.
abstract final class AppSpacing {
  static const double minimal = 4;
  static const double small = 8;
  static const double compact = 12;
  static const double standard = 16;
  static const double section = 24;
  static const double large = 32;

  // Preserve the established screen gutter on primary and secondary pages.
  static const double screen = 20;
}
