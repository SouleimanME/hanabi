/** Preparation des photos produit, dans le navigateur. */

/** Cote du visuel principal, en pixels. */
export const MAIN_SIZE = 1200;

/** Cote le plus long tolere pour une photo de galerie. */
export const GALLERY_MAX_SIDE = 1600;

/** Compromis poids / qualite du JPEG produit. */
const QUALITY = 0.82;

/** Charge une source (URL ou data URI) en image decodee. */
function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    // Necessaire si la source est distante : sans cela le canvas devient
    // « souille » et toDataURL leve une erreur de securite.
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Image illisible."));
    img.src = src;
  });
}

/** Prepare un canvas rempli de blanc. */
function makeCanvas(width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  // Lissage de meilleure qualite lors de la reduction.
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  return { canvas, ctx };
}

/** Recadre une photo sur un carre de `MAIN_SIZE`, centre, sans deformation.
 * @param {string} src URL ou data URI
 * @returns {Promise<string>} data URI JPEG de MAIN_SIZE x MAIN_SIZE
 */
export async function toCanonicalMain(src) {
  const img = await loadImage(src);
  const { canvas, ctx } = makeCanvas(MAIN_SIZE, MAIN_SIZE);

  // Cote de la zone carree prelevee dans la source : le plus petit des deux,
  // afin de rester a l'interieur de la photo.
  const side = Math.min(img.naturalWidth, img.naturalHeight);
  const sx = (img.naturalWidth - side) / 2;
  const sy = (img.naturalHeight - side) / 2;

  ctx.drawImage(img, sx, sy, side, side, 0, 0, MAIN_SIZE, MAIN_SIZE);
  return canvas.toDataURL("image/jpeg", QUALITY);
}

/** Reduit une photo sans la recadrer, cote le plus long plafonne.
 * @param {string} src URL ou data URI
 * @param {number} [maxSide]
 * @returns {Promise<string>} data URI JPEG
 */
export async function toGalleryImage(src, maxSide = GALLERY_MAX_SIDE) {
  const img = await loadImage(src);
  const { naturalWidth: w, naturalHeight: h } = img;

  // On n'agrandit jamais : le facteur est plafonne a 1.
  const scale = Math.min(1, maxSide / Math.max(w, h));
  const { canvas, ctx } = makeCanvas(Math.round(w * scale), Math.round(h * scale));

  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", QUALITY);
}

/** Poids approximatif, en octets, d'un data URI base64. */
export function dataUriBytes(dataUri) {
  const base64 = dataUri.slice(dataUri.indexOf(",") + 1);
  // 4 caracteres base64 codent 3 octets ; on retire le remplissage final.
  const padding = base64.endsWith("==") ? 2 : base64.endsWith("=") ? 1 : 0;
  return Math.round((base64.length * 3) / 4) - padding;
}
