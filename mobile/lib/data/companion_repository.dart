import '../models/companion.dart';
import '../models/content.dart';
import 'chat_repository.dart';
import 'api_client.dart';

class CompanionRepository {
  final FastApiChatRepository chat;
  final String? _owner;
  CompanionRepository(this.chat) : _owner = chat.account?.userId;
  ApiClient get api => chat.api;
  String? get token {
    if (chat.account?.userId != _owner)
      throw const ApiException('Your account changed. Reopen this activity.');
    return chat.account?.token;
  }

  Future<Map<String, dynamic>> discovery() =>
      api.get('/mobile/me/companion', token: token);
  Future<Lesson> guide(String id) async =>
      Lesson.fromJson(await api.get('/guides/$id'));
  Future<List<Lesson>> guides() async =>
      (await api.listAll('/guides')).map(Lesson.fromJson).toList();
  Future<void> progress(Lesson lesson, int step, {bool? completed}) async {
    await api.put('/mobile/me/progress/${lesson.id}', {
      if (completed != null) 'completed': completed,
      if (lesson.sections.isNotEmpty)
        'current_step_id': lesson.sections[step].id,
      'guide_revision': lesson.revision,
    }, token: token);
  }

  Future<ServicePlan> preview(String vehicleId) async => ServicePlan.fromJson(
    await api.post('/mobile/me/service-plans/preview', {
      'vehicle_id': vehicleId,
    }, token: token),
  );
  Future<ServicePlan> savePlan(ServicePlan plan) async => ServicePlan.fromJson(
    await api.post('/mobile/me/service-plans', {
      'vehicle_id': plan.vehicleId,
      'fingerprint': plan.fingerprint,
    }, token: token),
  );
  Future<ServicePlan> plan(String id) async => ServicePlan.fromJson(
    await api.get('/mobile/me/service-plans/$id', token: token),
  );
  Future<List<Map<String, dynamic>>> saved() =>
      api.listAll('/mobile/me/saved-items', token: token);
  Future<Map<String, dynamic>> save(Map<String, dynamic> item) =>
      api.post('/mobile/me/saved-items', item, token: token);
  Future<void> remove(String id) =>
      api.delete('/mobile/me/saved-items/$id', token: token);
  Future<Map<String, dynamic>> resume(
    String id, {
    String? messageId,
  }) => api.post(
    '/chat/sessions/$id/resume${messageId == null ? '' : '?message_id=$messageId'}',
    {},
    token: token,
  );
  Future<void> activity(
    String sessionId,
    Map<String, dynamic>? reference,
  ) async {
    await api.put('/chat/sessions/$sessionId/activity', {
      'activity': reference,
    }, token: token);
  }
}
