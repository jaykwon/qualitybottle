from bottle import route, request, run, static_file
import os
import subprocess
from pprint import pprint
import Image, ImageDraw, ImageEnhance
import math
from jinja2 import Environment, PackageLoader
env = Environment(loader=PackageLoader(__name__, 'templates'))

STAGING_DIR = './stage'
MINSTAGE = 'minstage/image'
MIN_RADIUS = r = 4
#MIN_QUALITY_THRESHOLD = 5
GREEN = "#00ff00"
YELLOW = "#ffff00"
RED = "#ff0000"
MIN_MAX_RED = 25
MIN_MAX_YELLOW = 50
DEGREE_SLICE = 11.25
MIN_LINE_LENGTH = MIN_RADIUS * 4

@route('/static/<filename>')
def server_static(filename):
    return static_file(filename, os.path.abspath(STAGING_DIR))

def get_minutia(original, contrast_boost):
    print "Contrast Boost: ", contrast_boost
    command = ['mindtct', '-m1', original, MINSTAGE]
    if contrast_boost:
        command.insert(2, '-b')
    print command
    try:
        subprocess.check_output(command)
        return True
    except subprocess.CalledProcessError:
        return False
        
def create_minutia_image(filename, min_qual, contrast_boost):
    if not get_minutia(filename, contrast_boost):
        print "Could not create minutia image for %s" % (filename)
        return None
    base = os.path.splitext(filename)[0]
    xyt = open(MINSTAGE + '.xyt', 'r')
    mn = open(MINSTAGE + '.min', 'r')
    for idx, line in enumerate(mn):
        if idx == 3:
            break
    img = Image.open(filename)
    img = img.convert("RGBA")
    if contrast_boost:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.75)
        del enhancer
    draw = ImageDraw.Draw(img)
    min_omit = 0
    print "Start_X Start_Y End_X End_Y Angle(d) Angle(NIST) Rads"
    for index, (xyt_line, min_line) in enumerate(zip(xyt, mn)):
        xyt_vals = xyt_line.rstrip().split(' ')
        min_vals = min_line.strip().replace(' ', '').split(':')
        assert int(min_vals[0]) == index, \
            'Zipped lists out of sync: %r, %r' % (int(min_vals[0]), index)
        x, y, theta, quality = [int(val) for val in xyt_vals]
        min_direction = float(min_vals[2]) * DEGREE_SLICE
        min_type = min_vals[4]
        assert min_type in ('BIF', 'RIG'), \
            'Min_Type not in tuple: %r' % (min_type)
        if quality < min_qual:
            min_omit += 1
            continue
        elif quality >= min_qual and quality < MIN_MAX_RED:
            color = RED
        elif quality >= MIN_MAX_RED and quality < MIN_MAX_YELLOW:
            color = YELLOW
        else:
            color = GREEN
        if min_type == 'RIG':
            draw.ellipse((x-r, y-r, x+r, y+r), outline=color)
        elif min_type == 'BIF':
            draw.rectangle([x-r, y-r, x+r, y+r], outline=color)
        min_direction = 90 - min_direction
        min_direction_rads = (min_direction * math.pi) / 180
        end_x = x + MIN_LINE_LENGTH * math.cos(min_direction_rads)
        end_y = y - MIN_LINE_LENGTH * math.sin(min_direction_rads)
        draw.line((x, y, round(end_x), round(end_y)), fill=color, width=1)
        #print x, y, round(end_x), round(end_y), min_direction, min_vals[2], \
        #    min_direction_rads, math.cos(min_direction_rads), \
        #    math.sin(min_direction_rads), math.cos(45), math.sin(45), \
        #    math.cos(math.pi / 4), math.sin(math.pi / 4)
    del draw
    xyt.close()
    img.save(os.path.join(base + "_pil.jpg"), "JPEG")
    return (index + 1, min_omit)

@route('/upload')
def upload():
    return '''
    <form action="/upload" method="post" enctype="multipart/form-data">
      Select a file:    <input type="file" name="data" />
      Min Quality:      <input type="text" name="min_qual" size="5" />
      Contrast Enhance: <input type="checkbox" name="contrast" value="True" />
      <input type="submit" value="Start upload" />
    </form>
    '''

@route('/upload', method='POST')
def do_upload():
    min_qual = request.forms.min_qual
    data = request.files.data
    contrast = bool(request.forms.contrast)
    if min_qual and data and data.file:
        raw = data.file.read()
        filename = data.filename
        filepath = os.path.join(STAGING_DIR, filename)
        base, ext = os.path.splitext(filename)
        with open(filepath, 'w') as file_to_save:
            file_to_save.write(raw)
        file_to_save.close()
        nfiq_score = subprocess.check_output(['nfiq'] + [filepath]).strip()
        min_total, min_omit = create_minutia_image(filepath, int(min_qual), 
                                                   contrast)
        return '''
        <html>       
          <h3>You uploaded %s (%d bytes).</h3>
          <img src="%s" />
          <h4><i>Contrast Enhancement (if necessary): %s</i></h4>
          <h4><i>Image created with minutia quality threshold of %s.</i></h4>
          <h3>Total Minutia: %s  Omitted Minutia: %s</h3>
          <h3>NFIQ: %s</h3>
        </html>
        ''' % (filename, len(raw), './static/' + base + '_pil.jpg',
               contrast, min_qual, min_total, min_omit, nfiq_score)
    return "You missed a field."
    
run(host='localhost', port=5000, debug=True)
