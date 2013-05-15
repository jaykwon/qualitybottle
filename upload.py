from bottle import route, request, run, static_file
import os
import subprocess
from pprint import pprint
import Image, ImageDraw

STAGING_DIR = './stage'
MINSTAGE = 'minstage/image'
MIN_RADIUS = r = 4
#MIN_QUALITY_THRESHOLD = 5
GREEN = "#00ff00"
YELLOW = "#ffff00"
RED = "#ff0000"
MIN_MAX_RED = 25
MIN_MAX_YELLOW = 50

@route('/static/<filename>')
def server_static(filename):
    return static_file(filename, os.path.abspath(STAGING_DIR))

def get_minutia(original):
    try:
        subprocess.check_output(['mindtct', '-m1', original, MINSTAGE])
        return True
    except subprocess.CalledProcessError:
        return False
        
def create_minutia_image(filename, min_qual):
    if not get_minutia(filename):
        print "Could not create minutia image for %s" % (filename)
        return None
    base = os.path.splitext(filename)[0]
    xyt = open(MINSTAGE + '.xyt', 'r')
    img = Image.open(filename)
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    min_omit = 0
    for index, line in enumerate(xyt):
        vals = line.rstrip().split(' ')
        x, y, theta, quality = [int(val) for val in vals]
        if quality < min_qual:
            min_omit += 1
            continue
        elif quality >= min_qual and quality < MIN_MAX_RED:
            color = RED
        elif quality >= MIN_MAX_RED and quality < MIN_MAX_YELLOW:
            color = YELLOW
        else:
            color = GREEN
        draw.ellipse((x-r, y-r, x+r, y+r), outline=color)
    del draw
    img.save(os.path.join(base + "_pil.jpg"), "JPEG")
    return (index, min_omit)

@route('/upload')
def upload():
    return '''
        <form action="/upload" method="post" enctype="multipart/form-data">
          Select a file:    <input type="file" name="data" />
          Min Quality:      <input type="text" name="min_qual" />
          <input type="submit" value="Start upload" />
        </form>
    '''

@route('/upload', method='POST')
def do_upload():
    min_qual = request.forms.min_qual
    data = request.files.data
    if min_qual and data and data.file:
        raw = data.file.read()
        filename = data.filename
        filepath = os.path.join(STAGING_DIR, filename)
        base, ext = os.path.splitext(filename)
        with open(filepath, 'w') as file_to_save:
            file_to_save.write(raw)
        file_to_save.close()
        nfiq_score = subprocess.check_output(['nfiq'] + [filepath]).strip()
        min_total, min_omit = create_minutia_image(filepath, int(min_qual))
        return '''
        <html>       
          <h3>You uploaded %s (%d bytes).</h3>
          <img src="%s" />
          <h4><i>Image created with minutia quality threshold of %s.</i></h4>
          <h3>Total Minutia: %s    Omitted Minutia: %s</h3>
          <h3>NFIQ: %s</h3>
        </html>
        ''' % (filename, len(raw), './static/' + base + '_pil.jpg',
               min_qual, min_total, min_omit, nfiq_score)
    return "You missed a field."
    
run(host='localhost', port=5000, debug=True)
