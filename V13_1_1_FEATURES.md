# v13.1.1 — train direction correction

The representative train SVGs are authored with the cab/front at the left side of the image. Earlier builds rotated the image as though its front were on the right, making the vehicle face backwards even while its position followed the correct track. v13.1.1 rotates the asset front onto the path tangent.

The real geographic renderer also validates each source polyline against the active station pair. If its endpoint order is opposite to travel, the polyline is reversed before the physical train body is sliced from it. Therefore the front end is always the end toward the next station.
