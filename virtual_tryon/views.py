import os
import base64
import uuid
import logging
import traceback
from io import BytesIO
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from PIL import Image
from products.models import Product
from .models import TryOnJob
from .serializers import TryOnJobSerializer
from ai_services.virtual_tryon import VirtualTryOnService

logger = logging.getLogger(__name__)
MAX_USER_IMAGE_BYTES = 10 * 1024 * 1024

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def generate_tryon_view(request):
    """
    Submits a photo and product for AI Virtual Try-On / Space Visualization.
    Completely resilient against missing files, format variances, and unauthenticated demo calls.
    """
    try:
        User = get_user_model()
        user = request.user if (request.user and request.user.is_authenticated) else (
            User.objects.filter(is_superuser=True).first() or User.objects.first()
        )

        product_id = request.data.get('product_id')
        mode = request.data.get('mode', 'clothing')

        if not product_id:
            return Response({'detail': 'product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        product = Product.objects.filter(id=product_id).first()
        if not product:
            return Response({'detail': f'Product with id {product_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure media directories exist
        try:
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'tryon_inputs'), exist_ok=True)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'tryon_results'), exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create media subdirectories: {e}")

        # 1. Obtain user image from multipart file or base64 payload
        user_file = request.FILES.get('user_image')
        base64_str = request.data.get('user_image_base64', '')
        raw_user_bytes = None

        if not user_file and not base64_str:
            return Response({'detail': 'Please upload a photo (user_image).'}, status=status.HTTP_400_BAD_REQUEST)

        if user_file:
            try:
                raw_user_bytes = user_file.read()
            except Exception:
                pass

        if not raw_user_bytes and base64_str:
            if base64_str.startswith('http'):
                # Download sample image
                import urllib.request
                try:
                    req = urllib.request.Request(base64_str, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        raw_user_bytes = resp.read()
                    filename = f"sample_{uuid.uuid4().hex[:8]}.jpg"
                    user_file = ContentFile(raw_user_bytes, name=filename)
                except Exception as e:
                    return Response({'detail': f'Could not load sample portrait: {e}'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    if ',' in base64_str:
                        base64_str = base64_str.split(',', 1)[1]
                    raw_user_bytes = base64.b64decode(base64_str)
                    filename = f"user_{user.id if user else 1}_{uuid.uuid4().hex[:8]}.jpg"
                    user_file = ContentFile(raw_user_bytes, name=filename)
                except Exception as e:
                    return Response({'detail': f'Invalid base64 image data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        if not raw_user_bytes:
            return Response({'detail': 'Could not decode photo bytes.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(raw_user_bytes) > MAX_USER_IMAGE_BYTES:
            return Response(
                {'detail': 'Photo is too large. Please upload an image under 10MB.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            with Image.open(BytesIO(raw_user_bytes)) as uploaded_image:
                uploaded_image.verify()
        except Exception:
            return Response(
                {'detail': 'The uploaded file is not a supported or readable image. Try a JPG, PNG, or WebP photo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            user_image=user_file if user_file else ContentFile(raw_user_bytes, name=f"user_{uuid.uuid4().hex[:8]}.jpg"),
            product_image_url=product_image_url,
            status='processing',
            metadata={'product_name': product.name}
        )

        # 3. Execute AI Try-On service passing bytes directly (in-memory)
        service = VirtualTryOnService()
        result = service.process_tryon(
            user_image_path=None,
            product_image_url=product_image_url,
            mode=mode,
            product_name=product.name,
            category_name=category_name,
            product_description=product.description or "",
            user_image_bytes=raw_user_bytes
        )

        if result.get('success') and result.get('image_bytes'):
            result_bytes = result['image_bytes']
            result_filename = f"tryon_res_{job.id}_{uuid.uuid4().hex[:8]}.jpg"
            try:
                job.result_image.save(result_filename, ContentFile(result_bytes), save=False)
            except Exception as e:
                # If disk save fails, save as data URI in result_image_url
                logger.warning(f"Result image disk save error: {e}")
                b64_res = base64.b64encode(result_bytes).decode('utf-8')
                job.result_image_url = f"data:image/jpeg;base64,{b64_res}"

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

    except Exception as exc:
        logger.error(f"[generate_tryon_view ERROR]: {traceback.format_exc()}")
        return Response({
            'detail': f'AI preview generation notice: {str(exc)}',
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def tryon_job_detail_view(request, job_id):
    """
    Retrieves status and generated result for a specific try-on job.
    """
    job = TryOnJob.objects.filter(id=job_id).first()
    if not job:
        return Response({'detail': 'Try-on job not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TryOnJobSerializer(job, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def tryon_history_view(request):
    """
    Returns try-on history.
    """
    if request.user and request.user.is_authenticated:
        jobs = TryOnJob.objects.filter(user=request.user).order_by('-created_at')[:20]
    else:
        jobs = TryOnJob.objects.all().order_by('-created_at')[:20]
    serializer = TryOnJobSerializer(jobs, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.AllowAny])
def delete_tryon_job_view(request, job_id):
    """
    Deletes a try-on record and cleans up associated images.
    """
    job = TryOnJob.objects.filter(id=job_id).first()
    if not job:
        return Response({'detail': 'Try-on job not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        if job.result_image and job.result_image.path:
            if os.path.exists(job.result_image.path):
                os.remove(job.result_image.path)
    except Exception:
        pass

    job.delete()
    return Response({'detail': 'Try-on entry deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)
