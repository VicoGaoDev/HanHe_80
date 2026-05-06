class GeneratedImage {
  const GeneratedImage({
    required this.id,
    required this.imageUrl,
    required this.previewUrl,
    required this.thumbUrl,
    required this.status,
    required this.errorMessage,
  });

  final int id;
  final String imageUrl;
  final String previewUrl;
  final String thumbUrl;
  final String status;
  final String errorMessage;

  factory GeneratedImage.fromJson(Map<String, dynamic> json) {
    return GeneratedImage(
      id: json['id'] as int? ?? 0,
      imageUrl: json['image_url'] as String? ?? '',
      previewUrl: json['preview_url'] as String? ?? '',
      thumbUrl: json['thumb_url'] as String? ?? '',
      status: json['status'] as String? ?? '',
      errorMessage: json['error_message'] as String? ?? '',
    );
  }
}

class TaskResult {
  const TaskResult({
    required this.id,
    required this.mode,
    required this.model,
    required this.source,
    required this.prompt,
    required this.numImages,
    required this.size,
    required this.resolution,
    required this.customSize,
    required this.creditCost,
    required this.status,
    required this.errorMessage,
    required this.createdAt,
    required this.images,
  });

  final String id;
  final String mode;
  final String model;
  final String source;
  final String prompt;
  final int numImages;
  final String size;
  final String resolution;
  final String customSize;
  final int creditCost;
  final String status;
  final String errorMessage;
  final String createdAt;
  final List<GeneratedImage> images;

  bool get isTerminal => status == 'success' || status == 'failed';

  factory TaskResult.fromJson(Map<String, dynamic> json) {
    return TaskResult(
      id: json['id'] as String? ?? '',
      mode: json['mode'] as String? ?? 'generate',
      model: json['model'] as String? ?? '',
      source: json['source'] as String? ?? 'web',
      prompt: json['prompt'] as String? ?? '',
      numImages: json['num_images'] as int? ?? 1,
      size: json['size'] as String? ?? '',
      resolution: json['resolution'] as String? ?? '',
      customSize: json['custom_size'] as String? ?? '',
      creditCost: json['credit_cost'] as int? ?? 0,
      status: json['status'] as String? ?? '',
      errorMessage: json['error_message'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      images: (json['images'] as List<dynamic>? ?? [])
          .map((item) => GeneratedImage.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}

class CreateTaskResponse {
  const CreateTaskResponse({
    required this.taskIds,
    this.taskId,
  });

  final String? taskId;
  final List<String> taskIds;

  factory CreateTaskResponse.fromJson(Map<String, dynamic> json) {
    return CreateTaskResponse(
      taskId: json['task_id'] as String?,
      taskIds: (json['task_ids'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
    );
  }
}
