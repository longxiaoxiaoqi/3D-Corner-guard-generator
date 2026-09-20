// U-shaped cover. mm. width is INNER width; height is INNER wall height.
width=100;
length=120;
height=15;
base=3;
wall=3;
assert(min(width,length,height,base,wall)>=0.2);
difference() {
    cube([length,width+2*wall,height+base]);
    translate([-1,wall,base]) cube([length+2,width,height+1]);
}
