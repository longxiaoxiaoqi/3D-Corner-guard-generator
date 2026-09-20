// Four-wall cover. mm. length, width and height are INNER dimensions.
width=100;
length=120;
height=15;
base=3;
wall=3;
assert(min(width,length,height,base,wall)>=0.2);
difference() {
    cube([length+2*wall,width+2*wall,height+base]);
    translate([wall,wall,base]) cube([length,width,height+1]);
}
