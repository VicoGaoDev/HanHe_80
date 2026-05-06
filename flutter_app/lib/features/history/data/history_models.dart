class HistoryImage {
  const HistoryImage({
    required this.id,
    required this.imageUrl,
    required this.previewUrl,
    required this.thumbUrl,
    required this.status,
  });

  final int id;
  final String imageUrl;
  final String previewUrl;
  final String thumbUrl;
  final String status;

  factory HistoryImage.fromJson(Map<String, dynamic> json) {
    return HistoryImage(
      id: json['id'] as int? ?? 0,
      imageUrl: json['image_url'] as String? ?? '',
      previewUrl: json['preview_url'] as String? ?? '',
      thumbUrl: json['thumb_url'] as String? ?? '',
      status: json['status'] as String? ?? '',
    );
  }
}

class UserHistoryCardItem {
  const UserHistoryCardItem({
    required this.taskId,
    required this.imageId,
    this.historyId,
    this.itemType = 'task',
    required this.prompt,
    required this.model,
    this.source = 'web',
    this.mode = 'generate',
    required this.status,
    required this.size,
    required this.resolution,
    this.numImages = 1,
    required this.creditCost,
    required this.createdAt,
    required this.imageUrl,
    required this.previewUrl,
    required this.thumbUrl,
    this.customSize = '',
    this.referenceImages = const [],
    required this.images,
  });

  final String? taskId;
  final int? imageId;
  final int? historyId;
  final String itemType;
  final String prompt;
  final String model;
  final String source;
  final String mode;
  final String status;
  final String size;
  final String resolution;
  final int numImages;
  final int creditCost;
  final String createdAt;
  final String imageUrl;
  final String previewUrl;
  final String thumbUrl;
  final String customSize;
  final List<String> referenceImages;
  final List<HistoryImage> images;

  factory UserHistoryCardItem.fromJson(Map<String, dynamic> json) {
    return UserHistoryCardItem(
      taskId: json['task_id'] as String?,
      imageId: json['image_id'] as int?,
      historyId: json['history_id'] as int?,
      itemType: json['item_type'] as String? ?? 'task',
      prompt: json['prompt'] as String? ?? '',
      model: json['model'] as String? ?? '',
      source: json['source'] as String? ?? 'web',
      mode: json['mode'] as String? ?? 'generate',
      status: json['status'] as String? ?? '',
      size: json['size'] as String? ?? '',
      resolution: json['resolution'] as String? ?? '',
      numImages: json['num_images'] as int? ?? 1,
      creditCost: json['credit_cost'] as int? ?? 0,
      createdAt: json['created_at'] as String? ?? '',
      imageUrl: json['image_url'] as String? ?? '',
      previewUrl: json['preview_url'] as String? ?? '',
      thumbUrl: json['thumb_url'] as String? ?? '',
      customSize: json['custom_size'] as String? ?? '',
      referenceImages: (json['reference_images'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      images: (json['images'] as List<dynamic>? ?? [])
          .map((item) => HistoryImage.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}

class UserHistoryResponse {
  const UserHistoryResponse({
    required this.total,
    required this.items,
  });

  final int total;
  final List<UserHistoryCardItem> items;

  factory UserHistoryResponse.fromJson(Map<String, dynamic> json) {
    return UserHistoryResponse(
      total: json['total'] as int? ?? 0,
      items: (json['items'] as List<dynamic>? ?? [])
          .map((item) => UserHistoryCardItem.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
