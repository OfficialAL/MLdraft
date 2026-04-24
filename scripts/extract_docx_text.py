import sys
import zipfile
import xml.etree.ElementTree as ET

def docx_text(path):
    with zipfile.ZipFile(path) as z:
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
    root = tree.getroot()
    # Word namespace
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    texts = [t.text for t in root.findall('.//w:t', ns) if t.text]
    return '\n'.join(texts)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python extract_docx_text.py path/to/file.docx')
        sys.exit(1)
    path = sys.argv[1]
    print(docx_text(path))
