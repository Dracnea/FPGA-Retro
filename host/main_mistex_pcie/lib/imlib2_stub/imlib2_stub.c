/* imlib2_stub.c -- the subset of Imlib2 Main_MiSTeX calls, as a stand-in for
 * hosts without libImlib2 (FPGA-Retro x86-64 build).  Image loading and
 * saving fail cleanly; in-memory images (the menu background layers and the
 * curtain) work, so the OSD/menu code paths run.  Blending is a plain copy of
 * the destination rectangle from the source (no scaling, no alpha); this
 * only affects the menu wallpaper, which nobody sees until the host video
 * viewer exists.  Replace with the real library when it is available.
 * SPDX-License-Identifier: BSD-2-Clause */
#include <stdlib.h>
#include <string.h>
#include "../imlib2/Imlib2.h"

struct stub_image { int w, h; DATA32 *data; int owns; char has_alpha; };
static struct stub_image *ctx = 0;

Imlib_Image imlib_load_image_with_error_return(const char *file, Imlib_Load_Error *error_return)
{
	(void)file;
	if (error_return) *error_return = IMLIB_LOAD_ERROR_NO_LOADER_FOR_FILE_FORMAT;
	return 0;
}

void imlib_context_set_image(Imlib_Image image) { ctx = (struct stub_image *)image; }

int imlib_image_get_width(void)  { return ctx ? ctx->w : 0; }
int imlib_image_get_height(void) { return ctx ? ctx->h : 0; }
DATA32 *imlib_image_get_data(void) { return ctx ? ctx->data : 0; }
void imlib_image_set_has_alpha(char has_alpha) { if (ctx) ctx->has_alpha = has_alpha; }
void imlib_image_orientate(int orientation) { (void)orientation; }

void imlib_free_image_and_decache(void)
{
	if (!ctx) return;
	if (ctx->owns) free(ctx->data);
	free(ctx);
	ctx = 0;
}

Imlib_Image imlib_create_image(int width, int height)
{
	struct stub_image *im = calloc(1, sizeof(*im));
	if (!im) return 0;
	im->w = width; im->h = height; im->owns = 1;
	im->data = calloc((size_t)width * height, sizeof(DATA32));
	if (!im->data) { free(im); return 0; }
	return im;
}

Imlib_Image imlib_create_image_using_data(int width, int height, DATA32 *data)
{
	struct stub_image *im = calloc(1, sizeof(*im));
	if (!im) return 0;
	im->w = width; im->h = height; im->data = data; im->owns = 0;
	return im;
}

Imlib_Image imlib_create_cropped_scaled_image(int source_x, int source_y, int source_width, int source_height,
                                              int destination_width, int destination_height)
{
	(void)source_x; (void)source_y; (void)source_width; (void)source_height;
	return imlib_create_image(destination_width, destination_height);
}

void imlib_blend_image_onto_image(Imlib_Image source_image, char merge_alpha,
                                  int source_x, int source_y, int source_width, int source_height,
                                  int destination_x, int destination_y, int destination_width, int destination_height)
{
	struct stub_image *src = (struct stub_image *)source_image;
	(void)merge_alpha; (void)source_width; (void)source_height;
	if (!src || !ctx || !src->data || !ctx->data) return;
	for (int y = 0; y < destination_height; y++) {
		int sy = source_y + y, dy = destination_y + y;
		if (sy < 0 || sy >= src->h || dy < 0 || dy >= ctx->h) continue;
		for (int x = 0; x < destination_width; x++) {
			int sx = source_x + x, dx = destination_x + x;
			if (sx < 0 || sx >= src->w || dx < 0 || dx >= ctx->w) continue;
			ctx->data[dy * ctx->w + dx] = src->data[sy * src->w + sx];
		}
	}
}

void imlib_save_image_with_error_return(const char *filename, Imlib_Load_Error *error_return)
{
	(void)filename;
	if (error_return) *error_return = IMLIB_LOAD_ERROR_NO_LOADER_FOR_FILE_FORMAT;
}
