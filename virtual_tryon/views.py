import base64
import uuid
from django.utils import timezone
from django.core.files.base import ContentFile
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from products.models import Product
from .models import TryOnJob
from .serializers import TryOnJobSerializer
from ai_services.virtual_tryon import VirtualTryOnService

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def generate_tryon_view(request):
    """
    Submits a photo and product for AI Virtual Try-On / Space Visualization.
    """
    user = request.user
    product_id = request.data.get('product_id')
    mode = request.data.get('mode', 'clothing')

    if not product_id:
        return Response({'detail': 'product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    product = Product.objects.filter(id=product_id).first()
    if not product:
        return Response({'detail': f'Product with id {product_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

    # 1. Obtain user image from multipart file or base64 payload
    user_file = request.FILES.get('user_image')
    base64_str = request.data.get('user_image_base64', '')

    if not user_file and not base64_str:
        return Response({'detail': 'Please upload a photo (user_image).'}, status=status.HTTP_400_BAD_REQUEST)

    if not user_file and base64_str:
        try:
            if ',' in base64_str:
                base64_str = base64_str.split(',', 1)[1]
            decoded_bytes = base64.b64decode(base64_str)
            filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}.jpg"
            user_file = ContentFile(decoded_bytes, name=filename)
        except Exception as e:
            return Response({'detail': f'Invalid base64 image data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate image file size (max 10MB)
    if user_file.size > 10 * 1024 * 1024:
        return Response({'detail': 'Uploaded image file exceeds maximum 10MB limit.'}, status=status.HTTP_400_BAD_REQUEST)

    # Canonical product image URL
    prod_img_obj = product.images.first()
    product_image_url = prod_img_obj.image_url if prod_img_obj else ""
    if not product_image_url:
        product_image_url = "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800"

    # Category name
    category_name = product.category.name if product.category else "Fashion"

    # 2. Create Job in database
    job = TryOnJob.objects.create(
        user=user,
        product=product,
        visualization_mode=mode,
        user_image=user_file,
        product_image_url=product_image_url,
        status='processing',
        metadata={'user_email': user.email, 'product_name': product.name}
    )

    # 3. Execute AI Try-On service
    service = VirtualTryOnService()
    result = service.process_tryon(
        user_image_path=job.user_image.path,
        product_image_url=product_image_url,
        mode=mode,
        product_name=product.name,
        category_name=category_name,
        product_description=product.description or ""
    )

    if result.get('success') and result.get('image_bytes'):
        result_bytes = result['image_bytes']
        result_filename = f"tryon_res_{job.id}_{uuid.uuid4().hex[:8]}.jpg"
        job.result_image.save(result_filename, ContentFile(result_bytes), save=False)
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.prompt_used = result.get('prompt', '')
        job.metadata.update(result.get('metadata', {}))
        job.save()
    else:
        job.status = 'failed'
        job.error_message = result.get('error', 'AI Virtual Try-On generation encountered an unexpected error.')
        job.completed_at = timezone.now()
        job.save()

    serializer = TryOnJobSerializer(job, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tryon_job_detail_view(request, job_id):
    """
    Retrieves status and generated result for a specific try-on job.
    """
    job = TryOnJob.objects.filter(id=job_id).first()
    if not job:
        return Response({'detail': 'Try-on job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if job.user != request.user and not request.user.is_staff:
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = TryOnJobSerializer(job, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tryon_history_view(request):
    """
    Lists the authenticated user's virtual try-on history.
    """
    jobs = TryOnJob.objects.filter(user=request.user).select_related('product', 'product__category')
    serializer = TryOnJobSerializer(jobs, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_tryon_job_view(request, job_id):
    """
    Deletes a try-on record and its associated images.
    """
    job = TryOnJob.objects.filter(id=job_id).first()
    if not job:
        return Response({'detail': 'Try-on job not found.'}, status=status.HTTP_404_NOT_FOUND)

    if job.user != request.user and not request.user.is_staff:
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    # Delete local files if exist
    try:
        if job.user_image and job.user_image.path:
            import os
            if os.path.exists(job.user_image.path):
                os.remove(job.user_image.path)
    except Exception:
        pass

    try:
        if job.result_image and job.result_image.path:
            import os
            if os.path.exists(job.result_image.path):
                os.remove(job.result_image.path)
    except Exception:
        pass

    job.delete()
    return Response({'message': 'Try-on entry deleted successfully.'}, status=status.HTTP_200_OK)

