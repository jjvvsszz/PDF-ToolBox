import os
import io
import numpy as np
import img2pdf
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image, ImageStat
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

POPPLER_PATH = r"F:\Downloads\poppler-25.12.0\Library\bin"

INPUT_PDF = r"F:\Downloads\comprimir.pdf"
OUTPUT_PDF = r"F:\Downloads\menor.pdf"
DPI_LEITURA = 150


# --- FUNÇÕES DE LÓGICA (Idênticas ao script anterior) ---

def is_page_color_or_photo(img_pil):
    """Decide se é foto (True) ou Texto (False)"""
    try:
        img_hsv = img_pil.convert('HSV')
        s = np.array(img_hsv)[:, :, 1]
        if np.mean(s) > 20: return True  # Saturação

        img_gray = img_pil.convert('L')
        stat = ImageStat.Stat(img_gray)
        if stat.var[0] > 3000: return True  # Variância/Textura
    except:
        return False
    return False


def processar_bloco(parametros):
    """
    Função que será executada pelos núcleos do processador.
    Recebe um intervalo de páginas (ex: pagina 10 a 20).
    """
    pdf_path, start, end, poppler_path = parametros

    # Extrai apenas o bloco de páginas necessário
    try:
        images = convert_from_path(pdf_path, dpi=DPI_LEITURA, first_page=start, last_page=end,
                                   poppler_path=poppler_path)
    except Exception as e:
        print(f"Erro no bloco {start}-{end}: {e}")
        return []

    processed_bytes = []

    for img in images:
        is_photo = is_page_color_or_photo(img)
        img_byte_arr = io.BytesIO()

        if is_photo:
            # Foto: Resize + JPEG Low Quality
            aspect = img.height / img.width
            new_w = 600
            new_h = int(new_w * aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            img.convert('RGB').save(img_byte_arr, format='JPEG', quality=15, optimize=True)
        else:
            # Texto: Threshold + CCITT Group 4
            fn = lambda x: 255 if x > 180 else 0
            img_bw = img.convert('L').point(fn, mode='1')
            img_bw.save(img_byte_arr, format='TIFF', compression='group4')

        processed_bytes.append(img_byte_arr.getvalue())

    # Retorna as imagens comprimidas e o índice para ordenar depois
    return (start, processed_bytes)


def main():
    if not os.path.exists(INPUT_PDF):
        print("Arquivo de entrada não encontrado.")
        return

    print(f"Analisando PDF: {INPUT_PDF}...")

    # Pega informações do PDF para saber quantas páginas tem
    try:
        info = pdfinfo_from_path(INPUT_PDF, poppler_path=POPPLER_PATH)
        total_pages = info["Pages"]
        print(f"Total de páginas: {total_pages}")
    except Exception as e:
        print(f"Erro ao ler info do PDF. Verifique o Poppler. Erro: {e}")
        return

    # Define o tamanho do bloco (chunk).
    # Blocos menores usam menos RAM, mas têm mais overhead de abertura de arquivo.
    # 10 a 20 páginas por bloco é um bom equilíbrio.
    chunk_size = 10
    chunks = []

    for i in range(1, total_pages + 1, chunk_size):
        end = min(i + chunk_size - 1, total_pages)
        chunks.append((INPUT_PDF, i, end, POPPLER_PATH))

    # Usa número de núcleos lógicos - 1 (para não travar o mouse)
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"Iniciando processamento paralelo com {max_workers} núcleos...")

    results = []

    # Inicia o Pool de Processos
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Envia as tarefas
        futures = executor.map(processar_bloco, chunks)

        count_done = 0
        for result in futures:
            if result:
                results.append(result)
                count_done += chunk_size
                print(f"Progresso estimado: {min(count_done, total_pages)}/{total_pages} páginas processadas...")

    print("Ordenando páginas e montando PDF final...")

    # Ordena os resultados pelo número da página inicial (start)
    results.sort(key=lambda x: x[0])

    final_pdf_bytes = []
    for _, pages_bytes in results:
        final_pdf_bytes.extend(pages_bytes)

    if final_pdf_bytes:
        with open(OUTPUT_PDF, "wb") as f:
            f.write(img2pdf.convert(final_pdf_bytes))

        size_mb = os.path.getsize(OUTPUT_PDF) / (1024 * 1024)
        print(f"Concluído! Tamanho Final: {size_mb:.2f} MB")
    else:
        print("Erro fatal: Nenhuma página foi processada corretamente.")


if __name__ == '__main__':
    # No Windows, multiprocessing exige que o código esteja dentro deste bloco
    main()