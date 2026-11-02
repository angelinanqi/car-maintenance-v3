import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/api_client.dart';

/// Obtain a fresh, account-authorized link when the user opens a manual.
class ManualSourceLink extends StatefulWidget {
  final String endpoint;
  final ApiClient api;
  final String? token;
  const ManualSourceLink({
    super.key,
    required this.endpoint,
    required this.api,
    this.token,
  });

  @override
  State<ManualSourceLink> createState() => _ManualSourceLinkState();
}

class _ManualSourceLinkState extends State<ManualSourceLink> {
  bool _opening = false;

  Future<void> _open() async {
    if (_opening) return;
    setState(() => _opening = true);
    try {
      final response = await widget.api.get(
        widget.endpoint,
        token: widget.token,
      );
      final uri = Uri.parse(response['url'] as String);
      if (!['https', 'http'].contains(uri.scheme) || uri.host.isEmpty) {
        throw const ApiException('Invalid manual link.');
      }
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw const ApiException('Could not open the manual.');
      }
    } catch (error) {
      if (mounted) {
        final message = error is ApiException
            ? error.message
            : 'Could not open the manual. Please try again.';
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(message)));
      }
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!RegExp(
      r'^/chat/sessions/[0-9a-f-]+/sources/[0-9a-f-]+/[0-9a-f-]+/original$',
    ).hasMatch(widget.endpoint)) {
      return const SizedBox.shrink();
    }
    return Align(
      alignment: Alignment.centerLeft,
      child: TextButton.icon(
        onPressed: _opening ? null : _open,
        icon: const Icon(Icons.menu_book_outlined, size: 20),
        label: Text(_opening ? 'Opening manual…' : 'Open manual'),
      ),
    );
  }
}
