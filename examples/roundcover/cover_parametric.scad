// mm; opening faces +Z. Inner diameter includes your chosen fitting clearance.
diameter=100;
height=15;
base=3;
wall=3;
opening_chamfer=1;
outer_radius=2;
inner_radius=2;
assert(diameter>=0.2 && diameter<=1000 && height>=0.2 && height<=1000);
assert(base>=0.2 && base<=1000 && wall>=0.2 && wall<=1000);
assert(opening_chamfer>=0 && opening_chamfer<wall);
assert(outer_radius>=0 && outer_radius<=min(base,wall));
assert(inner_radius>=0 && inner_radius<diameter/2);
assert(inner_radius+opening_chamfer<height);
r=diameter/2; R=r+wall; z=height+base;
ro=outer_radius; ri=inner_radius; c=opening_chamfer;
function quarter(v)=v>0?max(8,ceil(90/(2*acos(1-min(0.025/v,1))))):0;
no=quarter(ro); ni=quarter(ri);
$fn=max(128,4*ceil(180/acos(1-min(0.025/R,1))/4));
profile=concat([[0,0],[R-ro,0]],
    ro>0?[for(i=[1:no]) [R-ro+ro*cos(-90+90*i/no),ro+ro*sin(-90+90*i/no)]]:[],
    [[R,z],[r+c,z]], c>0?[[r,z-c]]:[], [[r,base+ri]],
    ri>0?[for(i=[1:ni]) [r-ri+ri*cos(-90*i/ni),base+ri+ri*sin(-90*i/ni)]]:[],
    [[0,base]]);
rotate_extrude(convexity=10) polygon(profile);
