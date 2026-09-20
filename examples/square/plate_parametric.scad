// mm. R: plan-view corner radius. C: 45-degree top/bottom edge bevel.
side=100; length=side; width=side; thickness=3;
radius=5; bevel=0.5;
round_plate=false;
assert(min(length,width,thickness)>0);
assert(radius>=0 && radius<=min(length,width)/2);
assert(bevel>=0 && bevel<min(length,width,thickness)/2);
function ring(z,d)=round_plate ?
    [for(i=[0:255]) [length/2+(length/2-d)*cos(i*360/256),width/2+(width/2-d)*sin(i*360/256),z]] :
    let(r=max(0,radius-d), centers=[[length-d-r,width-d-r],[d+r,width-d-r],[d+r,d+r],[length-d-r,d+r]])
    [for(j=[0:3]) for(i=[0:64]) [centers[j][0]+r*cos(j*90+i*90/64),centers[j][1]+r*sin(j*90+i*90/64),z]];
rings=bevel==0?[[0,0],[thickness,0]]:
    (!round_plate && radius>0 && radius<bevel)?
    [[0,bevel],[bevel-radius,radius],[bevel,0],[thickness-bevel,0],[thickness-bevel+radius,radius],[thickness,bevel]]:
    [[0,bevel],[bevel,0],[thickness-bevel,0],[thickness,bevel]];
n=round_plate?256:260; nr=len(rings);
v=concat([for(pair=rings) each ring(pair[0],pair[1])],[[length/2,width/2,0],[length/2,width/2,thickness]]);
faces=concat(
 [for(j=[0:nr-2]) for(i=[0:n-1]) each [[j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n],[j*n+i,(j+1)*n+(i+1)%n,(j+1)*n+i]]],
 [for(i=[0:n-1]) each [[nr*n,(i+1)%n,i],[nr*n+1,(nr-1)*n+i,(nr-1)*n+(i+1)%n]]]);
// Weld collapsed corner vertices when R=0 or C>=R, then drop zero-area faces.
vr=[for(p=v) [for(q=p) round(q*1000000)/1000000]];
unique=[for(i=[0:len(vr)-1]) if(search([vr[i]],vr)[0]==i) vr[i]];
mapped=[for(f=faces) [for(i=f) search([vr[i]],unique)[0]]];
// OpenSCAD uses clockwise face winding viewed from outside.
polyhedron(points=unique,faces=[for(f=mapped)
    if(norm(cross(unique[f[1]]-unique[f[0]],unique[f[2]]-unique[f[0]]))>0.000000001)
    [f[2],f[1],f[0]]],convexity=10);
