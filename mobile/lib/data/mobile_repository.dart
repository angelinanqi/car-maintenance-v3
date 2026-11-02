import 'api_client.dart';
import 'account_repository.dart';
import '../models/vehicle.dart';

// Personal-data endpoints are the Pass 3 contract. Failed calls are never
// replaced with demo data or local successful operations.
class MobileRepository {
  final ApiClient api;
  final AccountRepository account;
  MobileRepository(this.api, this.account);
  String get token {
    final value = account.token;
    if (value == null) {
      throw const ApiException('Sign in to continue.', statusCode: 401);
    }
    return value;
  }

  Future<List<CatalogueVehicle>> catalogue() async => (await api.listAll(
    '/mobile/vehicle-catalogue',
    totalTimeout: api.timeout,
  )).map(CatalogueVehicle.fromJson).where((v) => v.isIce).toList();
  Future<Map<String, dynamic>> snapshot() =>
      api.get('/mobile/me', token: token);
  Future<Map<String, dynamic>> learning() =>
      api.get('/mobile/me/learning', token: token);
  Future<Map<String, dynamic>> save(
    String collection,
    String id,
    Map<String, dynamic> data,
  ) => api.put(
    '/mobile/me/$collection/${Uri.encodeComponent(id)}',
    data,
    token: token,
  );
  Future<void> remove(String collection, String id) => api.delete(
    '/mobile/me/$collection/${Uri.encodeComponent(id)}',
    token: token,
  );
  Future<List<Map<String, dynamic>>> items() => api.listAll(
    '/mobile/maintenance-items',
    token: token,
    totalTimeout: api.timeout,
  );
}
