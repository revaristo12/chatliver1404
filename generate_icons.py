#!/usr/bin/env python3
"""
Script para gerar ícones do PWA CHATLIVER1404
Requer: pip install Pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    """Cria um ícone com o tamanho especificado"""
    # Criar imagem com fundo azul
    img = Image.new('RGBA', (size, size), (13, 110, 253, 255))  # Bootstrap primary blue
    
    # Criar objeto de desenho
    draw = ImageDraw.Draw(img)
    
    # Calcular tamanho do ícone de chat
    icon_size = int(size * 0.6)
    icon_x = (size - icon_size) // 2
    icon_y = (size - icon_size) // 2
    
    # Desenhar ícone de chat (simples)
    # Borda do chat
    border_width = max(2, size // 32)
    draw.rounded_rectangle(
        [icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
        radius=size // 8,
        fill=(255, 255, 255, 255),
        outline=(255, 255, 255, 255),
        width=border_width
    )
    
    # Desenhar bolhas de chat
    bubble_size = icon_size // 6
    bubble_spacing = bubble_size // 2
    
    # Primeira bolha (menor)
    bubble1_x = icon_x + icon_size // 4
    bubble1_y = icon_y + icon_size // 3
    draw.ellipse(
        [bubble1_x, bubble1_y, bubble1_x + bubble_size, bubble1_y + bubble_size],
        fill=(13, 110, 253, 255)
    )
    
    # Segunda bolha (média)
    bubble2_x = icon_x + icon_size // 2
    bubble2_y = icon_y + icon_size // 2
    draw.ellipse(
        [bubble2_x, bubble2_y, bubble2_x + bubble_size * 1.2, bubble2_y + bubble_size * 1.2],
        fill=(13, 110, 253, 255)
    )
    
    # Terceira bolha (maior)
    bubble3_x = icon_x + icon_size // 3
    bubble3_y = icon_y + icon_size // 1.5
    draw.ellipse(
        [bubble3_x, bubble3_y, bubble3_x + bubble_size * 1.5, bubble3_y + bubble_size * 1.5],
        fill=(13, 110, 253, 255)
    )
    
    # Salvar ícone
    img.save(filename, 'PNG')
    print(f"Ícone criado: {filename} ({size}x{size})")

def create_shortcut_icon(size, filename, text):
    """Cria um ícone de atalho com texto"""
    # Criar imagem com fundo azul
    img = Image.new('RGBA', (size, size), (13, 110, 253, 255))
    
    # Criar objeto de desenho
    draw = ImageDraw.Draw(img)
    
    # Tentar usar uma fonte do sistema
    try:
        # Tamanho da fonte baseado no tamanho do ícone
        font_size = size // 4
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Calcular posição do texto
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2
    
    # Desenhar texto
    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
    
    # Salvar ícone
    img.save(filename, 'PNG')
    print(f"Ícone de atalho criado: {filename} ({size}x{size})")

def main():
    """Função principal"""
    print("Gerando ícones para CHATLIVER1404 PWA...")
    
    # Criar diretório de ícones se não existir
    icons_dir = "static/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    # Tamanhos de ícones necessários
    icon_sizes = [16, 32, 72, 96, 128, 144, 152, 192, 384, 512]
    
    # Gerar ícones principais
    for size in icon_sizes:
        filename = os.path.join(icons_dir, f"icon-{size}x{size}.png")
        create_icon(size, filename)
    
    # Gerar ícones de atalho
    shortcuts = [
        ("shortcut-rooms.png", "S"),
        ("shortcut-explore.png", "E"),
        ("shortcut-create.png", "C")
    ]
    
    for filename, text in shortcuts:
        full_path = os.path.join(icons_dir, filename)
        create_shortcut_icon(96, full_path, text)
    
    print("\n✅ Todos os ícones foram gerados com sucesso!")
    print(f"📁 Localização: {icons_dir}/")
    print("\n📱 Agora você pode instalar o CHATLIVER1404 como um app no seu celular!")

if __name__ == "__main__":
    main()


