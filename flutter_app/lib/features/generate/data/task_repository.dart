import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/app_providers.dart';
import '../../../core/network/app_exception.dart';
import 'task_models.dart';

class TaskRepository {
  const TaskRepository(this._dio);

  final Dio _dio;

  Future<CreateTaskResponse> createTask({
    required String model,
    required String prompt,
    required int numImages,
    required String size,
    required String resolution,
    String customSize = '',
    List<String> referenceImages = const [],
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/tasks',
        data: {
          'mode': 'generate',
          'model': model,
          'source': 'app',
          'prompt': prompt,
          'num_images': numImages,
          'size': size,
          'resolution': resolution,
          'custom_size': customSize,
          'reference_images': referenceImages,
        },
      );
      return CreateTaskResponse.fromJson(response.data ?? {});
    } on DioException catch (error) {
      throw AppException.fromDioException(error);
    }
  }

  Future<List<TaskResult>> getTasks(List<String> taskIds) async {
    try {
      final query = taskIds.map((id) => 'task_ids=$id').join('&');
      final response = await _dio.get<List<dynamic>>('/tasks?$query');

      return (response.data ?? [])
          .map((item) => TaskResult.fromJson(item as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw AppException.fromDioException(error);
    }
  }
}

final taskRepositoryProvider = Provider<TaskRepository>((ref) {
  return TaskRepository(ref.watch(dioProvider));
});
