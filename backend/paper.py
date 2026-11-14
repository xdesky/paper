"""Physical paper sizes. Geometry is never scaled to fit a sheet."""
PAPERS = {'US Letter': (215.9, 279.4), 'A4': (210.0, 297.0)}


def configure_engine(engine, name='US Letter'):
    width, height = PAPERS[name]
    engine.PAGE_W, engine.PAGE_H = width, height
    engine.BODY = (8.0, 20.0, width-8, height-24.4)
    engine.PAPER_NAME = name
    engine.base.PAGE_W, engine.base.PAGE_H = width, height
    engine.base.BODY_X1, engine.base.BODY_Y1 = width-8, height-24.4
    return width, height


def printable_filename(name):
    return 'printable_a4.pdf' if name == 'A4' else 'printable_us_letter.pdf'
