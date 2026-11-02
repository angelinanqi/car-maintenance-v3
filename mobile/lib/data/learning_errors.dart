import 'api_client.dart';

class LearningRefreshFailure extends ApiException {
  final Object cause;
  LearningRefreshFailure(this.cause)
    : super('Your progress was saved, but could not be refreshed.');
}

String learningFailureMessage(Object error, {required String fallback}) {
  if (error is LearningRefreshFailure) {
    return 'Your progress was saved. ${learningFailureMessage(error.cause, fallback: 'Refresh progress before retrying. You can keep reading.')}';
  }
  if (error is ApiException) {
    switch (error.statusCode) {
      case 401:
        return 'Sign in again to save or refresh your learning progress. You can still read guides.';
      case 403:
        return 'Learning progress access is unavailable. Check your account and sign in again.';
      case 404:
        return 'This guide or category is no longer available. Refresh the learning library.';
      case 409:
        return 'The guide or your progress changed. Refresh progress and reopen the guide before retrying.';
      case 429:
        return 'Too many requests. Wait a moment before trying again.';
    }
  }
  return fallback;
}
