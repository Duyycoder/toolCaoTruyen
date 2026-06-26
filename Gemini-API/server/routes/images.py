"""
Routes for /v1/images/generations — image generation via Gemini.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import verify_api_key
from ..schemas import ImageData, ImageGenerationRequest, ImageGenerationResponse
from ..state import get_client

router = APIRouter()


@router.post("/v1/images/generations", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    _: str = Depends(verify_api_key),
):
    """
    Generate images using Gemini's image generation feature.
    Returns image URLs in OpenAI-compatible format.
    """
    client = get_client()

    try:
        response = await client.generate_content(
            f"Generate an image: {request.prompt}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini error: {str(e)}",
        )

    images = getattr(response, "images", [])
    if not images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Gemini did not return any images. "
                "Image generation may not be available for your account/region."
            ),
        )

    data = []
    for img in images[: request.n]:
        url = getattr(img, "url", None)
        data.append(ImageData(url=url, revised_prompt=request.prompt))

    return ImageGenerationResponse(data=data)
