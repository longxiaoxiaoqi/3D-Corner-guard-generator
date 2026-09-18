// Millimetres. arm = length along each PCB edge, excluding wall.
overlap = 2.2;
slot = 4.1;
top = 5;
bottom = 5;
arm = 15;
wall = 3;
mode = "single"; // "single" or "four"
c = min(0.8, wall/3, arm/10);
e = min(0.4, overlap/4, bottom/4, top/4);
eps = min(0.1, e/2);
h = bottom + slot + top;
assert(min(overlap,slot,top,bottom,arm,wall)>=0.2);
assert(arm>overlap);
module relief(poly) {
    translate([0,arm+eps,0]) rotate([90,0,0])
        linear_extrude(height=arm+eps) polygon(poly);
}
module cuts() {
    relief([[overlap-e,bottom],[overlap+eps,bottom-e-eps],
            [overlap+eps,bottom+eps],[overlap-e,bottom+eps]]);
    relief([[overlap-e,bottom+slot-eps],[overlap+eps,bottom+slot-eps],
            [overlap+eps,bottom+slot+e+eps],[overlap-e,bottom+slot]]);
}
module corner() {
    translate([wall,wall,0]) difference() {
        linear_extrude(height=h) polygon([
            [-wall+c,-wall],[arm-c,-wall],[arm,-wall+c],[arm,overlap],
            [overlap,overlap],[overlap,arm],[-wall+c,arm],
            [-wall,arm-c],[-wall,-wall+c]]);
        translate([0,0,bottom]) cube([arm+1,arm+1,slot]);
        cuts(); mirror([1,-1,0]) cuts();
    }
}
if(mode=="single") corner();
if(mode=="four") for(x=[0,arm+wall+6]) for(y=[0,arm+wall+6])
    translate([x,y,0]) corner();
