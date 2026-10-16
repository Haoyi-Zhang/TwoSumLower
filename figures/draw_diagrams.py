"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)

def generate(out):
    out.mkdir(parents=True,exist_ok=True)
    d=Drawing((-5.8,-6.7,5.8,.8))
    d.box('in',0,0,10.8,.95,'Two input words and an arbitrary initial flag mask')
    d.box('ordinary',-2.8,-1.85,5.05,1.5,'No input NaN\nRounded-value quotient\nFresh-flag correspondence')
    d.box('nan',2.8,-1.85,5.05,1.5,'At least one input NaN\nOrdered symbolic provenance\nInvalid-flag union')
    d.box('zero',-2.8,-4,5.05,1.5,'Exact zero-sign discharge\nIdentical ordered sum\nNo negative-zero residual')
    d.box('payload',2.8,-4,5.05,1.5,'Quieted output origin\nArbitrary payload and sign\nEight symbolic patterns')
    d.box('join',0,-5.9,10.8,1.1,'Equal output words and equal fresh flags\nSticky union extends equality to all initial flags')
    for a,b in [('in','ordinary'),('in','nan'),('ordinary','zero'),('nan','payload'),('zero','join'),('payload','join')]:
        d.edge(a,b)
    d.save(out,'proof-partition')
    d=Drawing((-4.1,-4,8,.9))
    d.box('raw',0,0,3.9,1.15,'Raw program\nsix named registers')
    d.box('quot',5.5,0,4.1,1.15,'Normalize terms\nerase register names')
    d.box('state',5.5,-2.5,4.1,1.3,'State $(R,M)$\nsix-term multiset + mask')
    d.box('goal',0,-2.5,3.9,1.3,'Relaxed goal\nordered sum + residual\nall events consumed',size=8.5)
    d.edge('raw','quot','e','w');d.text(2.75,.37,r'abstract $\alpha$',size=8)
    d.edge('quot','state');d.text(5.65,-1.25,'canonicalize',ha='left',size=8)
    d.edge('state','goal','w','e');d.text(2.75,-2.1,'destructive\nsuccessor',size=8)
    d.arrow(d.point('goal','w'),d.point('raw','w'),dashed=True,via=((-2.4,-2.5),(-2.4,0)))
    d.text(-2.65,-1.25,'raw proof\nrequired',ha='right',size=8)
    d.save(out,'abstraction')
    d=Drawing((-5.2,-6.9,7.2,.8))
    for name,x,y,label in [
        ('sem',0,0,'Operational semantics'),('bytes',4.8,0,'Byte decoding'),
        ('raw',0,-1.8,'All-word\nrefinement proof'),('member',4.8,-1.8,'Candidate class\nmembership'),
        ('lower',0,-3.6,'Two-barrier bound\nand relaxed replay'),('cost',4.8,-3.6,'Static cost facts'),
        ('theorem',2.4,-5.4,'Class minimum\nand attainment'),('tests',-3,-5.4,'Finite tests\nand mutations')]:
        d.box(name,x,y,3.5,1.0,label,size=8)
    d.edge('sem','raw');d.edge('bytes','member')
    d.edge('bytes','raw','s','ne')
    d.arrow(d.point('raw','w'),(1.6,-5.9),via=((-4.9,-1.8),(-4.9,-6.4),(1.6,-6.4)))
    d.arrow(d.point('member','e'),(3.2,-5.9),via=((6.9,-1.8),(6.9,-6.6),(3.2,-6.6)))
    d.edge('lower','theorem','s','nw');d.edge('cost','theorem','s','ne')
    d.edge('tests','theorem','e','w',dashed=True);d.text(-.3,-5.1,'attacks',size=8)
    d.save(out,'dependencies')

def main():
    import tempfile
    p=argparse.ArgumentParser(description='Direct Python TwoSum proof diagrams.')
    p.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as t:
            x,y=Path(t)/'a',Path(t)/'b';generate(x);generate(y)
            for name in ('proof-partition','abstraction','dependencies'):
                if (x/(name+'.pdf')).read_bytes()!=(y/(name+'.pdf')).read_bytes():
                    raise ValueError('Fresh vector redraws differ: '+name)
        print('Three proof diagrams: clipping and deterministic redraw checks passed.')
    else:generate(a.output_dir)
if __name__=='__main__':main()

