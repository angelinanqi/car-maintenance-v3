class Vehicle {
  final String id;
  final String name;
  final String model;
  final int year;
  final String engineSize;
  final String plateNumber;
  final int mileage;
  final String? carModel;
  final String? catalogueId;
  final String? knowledgeScopeId;
  final bool manualAvailable;
  final bool manufacturerScheduleAvailable;

  String get effectiveScope {
    return carModel ?? 'general';
  }

  const Vehicle({
    required this.id,
    required this.name,
    required this.model,
    required this.year,
    required this.engineSize,
    required this.plateNumber,
    required this.mileage,
    this.carModel,
    this.catalogueId,
    this.knowledgeScopeId,
    this.manualAvailable = false,
    this.manufacturerScheduleAvailable = false,
  });

  factory Vehicle.fromJson(Map<String, dynamic> json) => Vehicle(
    id: json['id'] as String,
    name: json['name'] as String,
    model: json['model'] as String,
    year: json['year'] as int,
    engineSize: json['engineSize'] as String,
    plateNumber: json['plateNumber'] as String,
    mileage: json['mileage'] as int,
    carModel: json['carModel'] as String?,
    catalogueId: json['catalogueId'] as String?,
    knowledgeScopeId: json['knowledgeScopeId'] as String?,
    manualAvailable: json['manualAvailable'] == true,
    manufacturerScheduleAvailable:
        json['manufacturerScheduleAvailable'] == true,
  );

}

class CatalogueVehicle {
  final String id, manufacturer, model, variant, engine, powertrain;
  final int year;
  const CatalogueVehicle({
    required this.id,
    required this.manufacturer,
    required this.model,
    required this.year,
    required this.variant,
    required this.engine,
    required this.powertrain,
  });
  String get label => '$manufacturer $model $year $variant';
  bool get isIce => powertrain == 'petrol' || powertrain == 'diesel';
  factory CatalogueVehicle.fromJson(Map<String, dynamic> data) =>
      CatalogueVehicle(
        id: data['id'] as String,
        manufacturer: data['manufacturer'] as String,
        model: data['model'] as String,
        year: data['year'] as int,
        variant: data['variant'] as String,
        engine: data['engine'] as String,
        powertrain: data['powertrain'] as String,
      );
}
