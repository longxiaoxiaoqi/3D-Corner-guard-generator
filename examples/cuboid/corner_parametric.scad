// Cuboid three-face guard. Units: mm. Lengths exclude wall.
x=20;
y=25;
z=30;
wall=3;
mode="single"; // "single", "mirrored", "eight"
assert(min(x,y,z,wall)>=0.2);
module corner() {
    difference() {
        cube([x+wall,y+wall,z+wall]);
        translate([wall,wall,wall]) cube([x+1,y+1,z+1]);
    }
}
module reflected() { translate([x+wall,0,0]) mirror([1,0,0]) corner(); }
if(mode=="single") corner();
if(mode=="mirrored") reflected();
if(mode=="eight") for(row=[0:1]) for(col=[0:3])
    translate([col*(x+wall+6),row*(y+wall+6),0])
        if(col%2==0) corner(); else reflected();
