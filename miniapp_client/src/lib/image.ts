/**
 * Rasmni yuborishdan OLDIN kichraytirish.
 *
 * Nega kerak: telefon kamerasi 8-12 MB rasm beradi. Aidentika limiti ~15 MB
 * (base64 da hajm yana ~33% oshadi), ya'ni xom rasm limitdan oshib ketadi va
 * mijoz "413 image_too_large" oladi. Bundan tashqari mobil internetda katta
 * rasm sekin ketadi. 2000px generatsiya sifati uchun yetarlidan ortiq.
 */

const MAX_SIDE = 2000;
const QUALITY = 0.9;

export type Prepared = { data: string; media_type: string; preview: string };

export async function prepareImage(file: File): Promise<Prepared> {
  if (!file.type.startsWith("image/")) {
    throw new Error("Faqat rasm fayli yuborish mumkin");
  }

  const bitmap = await loadBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Rasmni tayyorlab bo'lmadi");
  ctx.drawImage(bitmap as any, 0, 0, w, h);

  // JPEG — hajm uchun. Shaffoflik kerak bo'lsa PNG ga o'tish mumkin.
  const dataUrl = canvas.toDataURL("image/jpeg", QUALITY);
  const base64 = dataUrl.split(",")[1] || "";

  return { data: base64, media_type: "image/jpeg", preview: dataUrl };
}

async function loadBitmap(file: File): Promise<ImageBitmap | HTMLImageElement> {
  // createImageBitmap tezroq, lekin eski Safari'da yo'q — zaxira yo'l bilan
  if (typeof createImageBitmap === "function") {
    try {
      return await createImageBitmap(file);
    } catch { /* zaxiraga o'tamiz */ }
  }
  return await new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Rasm ochilmadi")); };
    img.src = url;
  });
}
