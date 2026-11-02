import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:html/parser.dart' as html;
import 'package:html/dom.dart' as dom;
import 'package:url_launcher/url_launcher.dart';
import '../data/api_client.dart';

class ChatAttachment extends StatefulWidget {
  final Map<String, dynamic> attachment;
  final ApiClient api;
  final String? token;
  const ChatAttachment({
    super.key,
    required this.attachment,
    required this.api,
    this.token,
  });
  @override
  State<ChatAttachment> createState() => _ChatAttachmentState();
}

class _ChatAttachmentState extends State<ChatAttachment> {
  Future<Uint8List>? _image;
  bool _opening = false;

  @override
  void initState() {
    super.initState();
    _loadImage();
  }

  void _loadImage() {
    _image = null;
    if (widget.attachment['kind'] == 'table' &&
        widget.attachment['asset_available'] == false) {
      return;
    }
    if (widget.attachment['asset_endpoint'] != null) {
      _image = widget.api.chatImageBytes(
        widget.attachment['asset_endpoint'] as String? ?? '',
        widget.token,
      );
    }
  }

  String _title() {
    final review = widget.attachment['identity_review'];
    if (review is Map && (review['title'] as String? ?? '').isNotEmpty) {
      return review['title'] as String;
    }
    final generated = widget.attachment['generated_identity'];
    if (generated is Map && (generated['title'] as String? ?? '').isNotEmpty) {
      return generated['title'] as String;
    }
    final caption = widget.attachment['caption'] as String? ?? '';
    if (caption.isNotEmpty) return caption;
    final sections = widget.attachment['section_path'] as List? ?? [];
    if (sections.isNotEmpty) return '${sections.last}';
    return widget.attachment['kind'] == 'table'
        ? 'Source table'
        : 'Source image';
  }

  Future<void> _original() async {
    if (_opening) return;
    setState(() => _opening = true);
    try {
      final endpoint = widget.attachment['source_endpoint'] as String? ?? '';
      if (!endpoint.startsWith('/chat/sessions/') ||
          !endpoint.endsWith('/original') ||
          endpoint.contains('..')) {
        throw const ApiException('Invalid source reference.');
      }
      final response = await widget.api.get(endpoint, token: widget.token);
      var uri = Uri.parse(response['url'] as String);
      if (!['http', 'https'].contains(uri.scheme) || uri.host.isEmpty) {
        throw const ApiException('Invalid original source URL.');
      }
      final pages = widget.attachment['pages'] as List? ?? [];
      if (pages.isNotEmpty) {
        uri = uri.replace(fragment: 'page=${pages.first}');
      }
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw const ApiException('Could not open the original source.');
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not open the original source. Check your connection and try again.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  void _expand(Widget child) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          appBar: AppBar(title: Text(_title())),
          body: SafeArea(child: Center(child: child)),
        ),
      ),
    );
  }

  Widget _imageView(Uint8List bytes, {bool expanded = false}) {
    final image = Image.memory(
      bytes,
      cacheWidth: expanded
          ? null
          : (MediaQuery.sizeOf(context).width *
                    MediaQuery.devicePixelRatioOf(context))
                .clamp(320, 1440)
                .round(),
      fit: BoxFit.contain,
      semanticLabel: _title(),
      errorBuilder: (_, _, _) => const Text(
        'The source image could not be decoded. Open the original source.',
      ),
    );
    if (expanded) return image;
    return InkWell(
      onTap: () => _openImage(bytes),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(width: double.infinity, height: 160, child: image),
      ),
    );
  }

  void _openImage(Uint8List bytes) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        fullscreenDialog: true,
        builder: (viewerContext) => Scaffold(
          backgroundColor: Colors.black,
          body: SafeArea(
            child: Stack(
              fit: StackFit.expand,
              children: [
                InteractiveViewer(
                  minScale: 1,
                  maxScale: 6,
                  child: Center(
                    child: Image.memory(
                      bytes,
                      fit: BoxFit.contain,
                      semanticLabel: _title(),
                      errorBuilder: (_, _, _) => const Padding(
                        padding: EdgeInsets.all(16),
                        child: Text(
                          'The source image could not be decoded. Open the original source.',
                          style: TextStyle(color: Colors.white),
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  top: 8,
                  right: 8,
                  child: IconButton(
                    tooltip: 'Close image',
                    constraints: const BoxConstraints(
                      minWidth: 48,
                      minHeight: 48,
                    ),
                    style: IconButton.styleFrom(
                      backgroundColor: Colors.black54,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => Navigator.of(viewerContext).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.attachment;
    final pages = (a['pages'] as List? ?? []).join(', ');
    final sections = a['section_path'] as List? ?? [];
    final hasTableImage =
        a['kind'] == 'table' &&
        a['asset_endpoint'] != null &&
        a['asset_available'] != false;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_title(), style: Theme.of(context).textTheme.titleSmall),
            if (a['reference_label'] != null)
              Text('Reference ${a['reference_label']}'),
            Text(
              '${a['document_title'] ?? 'Manual'}${pages.isEmpty ? ', page unavailable' : ', pages $pages'}',
            ),
            if (sections.isNotEmpty && '${sections.last}' != _title())
              Text('${sections.last}'),
            if (a['kind'] == 'image' || hasTableImage)
              FutureBuilder<Uint8List>(
                future: _image,
                builder: (context, snapshot) {
                  if (_image == null) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Text(
                        'Image unavailable. Open the original source to view it.',
                      ),
                    );
                  }
                  if (snapshot.hasError) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Image unavailable. Check your connection or source access.',
                        ),
                        TextButton(
                          onPressed: () => setState(_loadImage),
                          child: const Text('Retry image'),
                        ),
                      ],
                    );
                  }
                  if (!snapshot.hasData) {
                    return const SizedBox(
                      height: 160,
                      child: Center(
                        child: CircularProgressIndicator(
                          semanticsLabel: 'Loading source image',
                        ),
                      ),
                    );
                  }
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _imageView(snapshot.data!),
                      TextButton(
                        onPressed: () => _openImage(snapshot.data!),
                        child: const Text('Enlarge image'),
                      ),
                    ],
                  );
                },
              ),
            if (a['kind'] == 'table' && a['structure_valid'] == true) ...[
              if (!hasTableImage)
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 240),
                  child: SourceTable(sourceHtml: a['html'] as String? ?? ''),
                ),
              TextButton(
                onPressed: () => _expand(
                  SourceTable(
                    sourceHtml: a['html'] as String? ?? '',
                    expanded: true,
                  ),
                ),
                child: const Text('Expand table'),
              ),
            ],
            if (a['kind'] == 'table' && a['structure_valid'] != true)
              const Text(
                'The extracted layout is unreliable. Use the original source for this table.',
              ),
            for (final note in a['notes'] as List? ?? []) Text('$note'),
            if ((a['context'] as List? ?? []).isNotEmpty)
              ExpansionTile(
                title: const Text('Source context'),
                children: [
                  for (final paragraph in a['context'] as List)
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Text('$paragraph'),
                    ),
                ],
              ),
            if (a['kind'] == 'table' && a['source_fidelity_verified'] != true)
              const Text(
                'Extraction fidelity is unverified. Check symbols, notes and vehicle applicability against the original.',
              ),
            if (a['kind'] == 'table' &&
                a['association_verified'] != true &&
                (a['notes'] as List? ?? []).isNotEmpty)
              const Text(
                'Nearby notes are included as context; their association needs verification.',
              ),
            TextButton(
              onPressed: _opening ? null : _original,
              child: Text(
                _opening ? 'Opening source…' : 'Open original source',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Render the preserved sanitized HTML, including explicit merged cells.
/// Fixed column widths and measured row heights keep navigation predictable.
class SourceTable extends StatelessWidget {
  final String sourceHtml;
  final bool expanded;
  const SourceTable({
    super.key,
    required this.sourceHtml,
    this.expanded = false,
  });

  String _cellText(dom.Node node) {
    if (node is dom.Text) return node.data;
    if (node is dom.Element && node.localName == 'br') return '\n';
    final text = node.nodes.map(_cellText).join();
    if (node is dom.Element && ['p', 'div', 'li'].contains(node.localName)) {
      return '$text\n';
    }
    return text;
  }

  @override
  Widget build(BuildContext context) {
    final table = html.parseFragment(sourceHtml).querySelector('table');
    if (table == null) return const Text('Table unavailable.');
    final rows = table.querySelectorAll('tr');
    if (rows.length > 1000 || sourceHtml.length > 1000000) {
      return const Text(
        'This table is too large for inline display. Open the original source.',
      );
    }
    final cells = <Map<String, dynamic>>[];
    final occupied = <String>{};
    var columns = 0;
    for (var r = 0; r < rows.length; r++) {
      var c = 0;
      for (final cell in rows[r].children.where(
        (e) => ['td', 'th'].contains(e.localName),
      )) {
        while (occupied.contains('$r:$c')) {
          c++;
        }
        final rs = int.tryParse(cell.attributes['rowspan'] ?? '1') ?? 1;
        final cs = int.tryParse(cell.attributes['colspan'] ?? '1') ?? 1;
        if (rs < 1 || cs < 1 || r + rs > rows.length || c + cs > 100) {
          return const Text(
            'Unsupported table layout. Open the original source.',
          );
        }
        for (var rr = r; rr < r + rs; rr++) {
          for (var cc = c; cc < c + cs; cc++) {
            occupied.add('$rr:$cc');
          }
        }
        cells.add({
          'row': r,
          'column': c,
          'rowspan': rs,
          'colspan': cs,
          'text': _cellText(cell).trim(),
          'header': cell.localName == 'th',
        });
        c += cs;
        if (c > columns) columns = c;
      }
    }
    if (columns == 0) return const Text('Table has no displayable cells.');
    const width = 145.0;
    final heights = List<double>.filled(rows.length, 40);
    final style =
        Theme.of(context).textTheme.bodyMedium ?? const TextStyle(fontSize: 14);
    for (final cell in cells) {
      final painter = TextPainter(
        text: TextSpan(text: cell['text'] as String, style: style),
        textDirection: Directionality.of(context),
        textScaler: MediaQuery.textScalerOf(context),
      )..layout(maxWidth: width * (cell['colspan'] as int) - 16);
      final r = cell['row'] as int;
      final span = cell['rowspan'] as int;
      final current = heights
          .sublist(r, r + span)
          .fold<double>(0, (a, b) => a + b);
      if (painter.height + 16 > current) {
        final extra = (painter.height + 16 - current) / span;
        for (var i = r; i < r + span; i++) {
          heights[i] += extra;
        }
      }
      painter.dispose();
    }
    final tops = <double>[0];
    for (final h in heights) {
      tops.add(tops.last + h);
    }
    final content = SizedBox(
      width: columns * width,
      height: tops.last,
      child: Stack(
        children: [
          for (final cell in cells)
            Positioned(
              left: (cell['column'] as int) * width,
              top: tops[cell['row'] as int],
              width: (cell['colspan'] as int) * width,
              height:
                  tops[(cell['row'] as int) + (cell['rowspan'] as int)] -
                  tops[cell['row'] as int],
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: Theme.of(context).dividerColor),
                  color: cell['header'] == true
                      ? Theme.of(context).colorScheme.surfaceContainerHighest
                      : null,
                ),
                child: Text(cell['text'] as String, style: style),
              ),
            ),
        ],
      ),
    );
    final scroll = SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SingleChildScrollView(child: content),
    );
    return expanded
        ? InteractiveViewer(minScale: 0.5, maxScale: 3, child: scroll)
        : scroll;
  }
}
