# ecommerce-backened

## Optional local virtual try-on (no API key)

The backend defaults to local image inference and does not call OpenRouter unless
`TRYON_PROVIDER=openrouter` is explicitly set. Clothing previews can use the
open-source FASHN VTON v1.5 pipeline. It needs its model files (about 2 GB),
PyTorch, and a suitable GPU for practical response times; set
`FASHN_VTON_WEIGHTS_DIR` to the downloaded weights directory. The Render service
does not include these weights or a GPU, so install/configure local inference on
a GPU host before enabling try-on there. Without the weights, the API returns a
setup message instead of charging an image API. FASHN VTON supports tops,
bottoms, and one-piece garments; shoes, accessories, and room placement need a
different image-edit model.

The FASHN VTON code and primary weights are Apache-2.0. Review the licenses of
all helper components and training datasets before commercial use.
