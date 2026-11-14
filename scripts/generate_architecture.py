"""Generate a schematic architecture diagram; no empirical result is implied."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

def make():
    root=Path(__file__).resolve().parents[1]
    target=root/'results'/'00_arquitectura.png'
    target.parent.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(13.2,3.1),dpi=160)
    ax.set_xlim(0,13.2);ax.set_ylim(0,3.1);ax.axis('off')
    titles=['IBM Telco\nCSV verificado','Calidad / EDA\n15 entradas','Preparación\nTrain 64 %','3 ML + 3 DL\nValidación 16 %','Selección\nTest 20 %']
    xs=[.2,2.8,5.4,8.0,10.6]
    for x,txt in zip(xs,titles):
        box=FancyBboxPatch((x,1.35),2.37,.9,boxstyle='round,pad=0.11,rounding_size=0.12',linewidth=1.1,facecolor='#edf5f7',edgecolor='#39647a')
        ax.add_patch(box);ax.text(x+1.19,1.80,txt,ha='center',va='center',fontsize=10,color='#163d53',weight='semibold')
    for i in range(4):
        arrow=FancyArrowPatch((xs[i]+2.45,1.79),(xs[i+1]-.09,1.79),arrowstyle='-|>',mutation_scale=15,lw=1.5,color='#487b8a')
        ax.add_patch(arrow)
    ax.text(6.6,.6,'Balanceo exclusivamente en train   |   SHAP para explicar predicciones   |   FastAPI + frontend + monitoreo',ha='center',va='center',fontsize=10,color='#3b5060')
    ax.set_title('Arquitectura de la solución y protocolo de evaluación',fontsize=15,color='#163d53',pad=12,weight='bold')
    fig.tight_layout()
    fig.savefig(target,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    print(target)
if __name__=='__main__':make()
