from PIL import Image, ImageDraw, ImageFont
import textwrap
import os


class LocalImageAdapter:
    def __init__(self, canvas_size=(1080, 1080), bg_color=(235, 245, 255)):
        # По умолчанию делаем приятный светло-голубой фон (как небо в Canva)
        # В будущем сюда можно передавать путь к красивой картинке-фону
        self.canvas_size = canvas_size
        self.bg_color = bg_color

    def generate_infographic(self, title_text: str, description_text: str, product_image_path: str,
                             output_path: str) -> str:
        print("🎨 Запускаем локальную генерацию инфографики...")

        # 1. Создаем холст
        canvas = Image.new('RGB', self.canvas_size, color=self.bg_color)
        draw = ImageDraw.Draw(canvas)

        # 2. Пытаемся загрузить красивый шрифт (если его нет — берем дефолтный)
        # Для продакшена лучше скачать .ttf файл (например, Montserrat-Bold.ttf) и положить в папку проекта
        try:
            title_font = ImageFont.truetype("arial.ttf", 70)
            desc_font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            title_font = ImageFont.load_default()
            desc_font = ImageFont.load_default()

        # 3. Рисуем заголовок (с переносом строк, если он длинный)
        wrapped_title = textwrap.fill(title_text, width=25)
        draw.multiline_text((100, 100), wrapped_title, font=title_font, fill=(20, 20, 20), spacing=10)

        # 4. Рисуем описание
        wrapped_desc = textwrap.fill(description_text, width=40)
        draw.multiline_text((100, 300), wrapped_desc, font=desc_font, fill=(70, 70, 70), spacing=10)

        # 5. Накладываем фото товара (наушников)
        if os.path.exists(product_image_path):
            product_img = Image.open(product_image_path).convert("RGBA")

            # Масштабируем фото товара, чтобы оно влезло в нижнюю часть (например, 600x600)
            product_img.thumbnail((600, 600))

            # Вычисляем координаты, чтобы разместить фото по центру снизу
            x_pos = (self.canvas_size[0] - product_img.width) // 2
            y_pos = self.canvas_size[1] - product_img.height - 50

            # Накладываем (маска нужна для прозрачного фона PNG)
            canvas.paste(product_img, (x_pos, y_pos), product_img)
        else:
            print(f"⚠️ Фото товара не найдено по пути: {product_image_path}")

        # 6. Сохраняем результат
            canvas.save(output_path, qual                   ity=95)
            print(f"✅ Инфографика успешно сохранена: {output_path}")
        return output_path


# --- Блок для быстрого теста ---
if __name__ == "__main__":
    adapter = LocalImageAdapter()
    # Замени "headphones.png" на реальный путь к твоему фото товара (желательно без фона)
    adapter.generate_infographic(
        title_text="Беспроводные наушники Pro",
        description_text="Идеальный звук. Активное шумоподавление. До 30 часов работы без подзарядки.",
        product_image_path="headphones.png",
        output_path="final_infographic.jpg"
    )