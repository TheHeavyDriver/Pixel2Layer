# Project Description — Image-to-Editable Design Platform

## 1. Project Overview

This project is a web-based design platform that converts **flattened image files such as PNG, JPG, and JPEG into editable, structured designs**.

Normally, when a design is exported as an image, all of its components are flattened into pixels. A user can view the image, resize the entire image, or apply basic filters, but they cannot independently modify the individual elements inside it.

For example, a poster exported as a PNG may contain:

* Text
* Logos
* Icons
* Shapes
* Illustrations
* Backgrounds
* Images
* Decorative elements
* Colors and gradients

After flattening, all of these elements become part of the same raster image.

The goal of this project is to **reverse that flattening process as much as technically possible**.

The application analyzes an uploaded image, identifies its visual components, reconstructs them as separate editable objects, and loads the resulting structure into a browser-based design editor.

The user can then manually modify the reconstructed design using familiar design-tool interactions such as selecting, moving, resizing, rotating, recoloring, editing text, changing fonts, modifying shapes, and managing layers.

The application does **not** rely on users giving AI commands to perform edits. AI and computer-vision techniques are used primarily during the **image reconstruction/import stage**. Once the design has been reconstructed, the user has direct control over every detected element.

---

# 2. Core Concept

The central concept of the application is:

**Raster Image → Visual Analysis → Element Extraction → Editable Scene Graph → Design Editor**

Instead of treating the uploaded image as a single object, the application attempts to understand its internal structure.

For example, an uploaded poster might be reconstructed as:

```text
Poster
│
├── Background
│
├── Logo
│
├── Heading
│   ├── Text
│   ├── Font
│   ├── Size
│   ├── Color
│   └── Position
│
├── Subtitle
│
├── Decorative Circle
│
├── Product Image
│
└── Decorative Shapes
```

Each element becomes an independent object in the editor.

The user can then select the heading and change its text, font, size, color, position, or rotation without affecting the rest of the design.

---

# 3. Problem Statement

Most images used on the web are distributed as flattened raster files.

For example:

```text
poster.png
banner.jpg
flyer.jpeg
social-media-post.png
```

Once exported, the original editable structure is usually lost.

If a designer receives only the final image and wants to make a small change, they may have to:

1. Find the original design file.
2. Ask the original designer for the source.
3. Recreate the design manually.
4. Use Photoshop or another editor to remove and replace elements.
5. Reconstruct typography, shapes, and positioning.

This can be extremely time-consuming.

The proposed application attempts to solve this problem by automatically reconstructing the visual structure of a flattened image and presenting it as an editable document.

---

# 4. Main Objective

The primary objective is to build a system that can take an image such as:

```text
input.png
```

and produce an editable document such as:

```text
Editable Design
│
├── Background
├── Text Layer
├── Shape Layer
├── Vector Layer
├── Image Layer
└── Decorative Elements
```

The reconstructed document should preserve the original design's:

* Layout
* Relative positioning
* Colors
* Typography
* Shapes
* Images
* Layer relationships
* Scale
* Rotation
* Visual appearance

as accurately as possible.

---

# 5. Important Product Philosophy

The project is **not an AI chatbot for image editing**.

The user does not need to type commands such as:

> "Make the heading blue."

Instead, the user interacts directly with the design.

For example:

```text
Select Heading
       ↓
Properties Panel
       ↓
Font: Poppins
Size: 64px
Color: #FFFFFF
Weight: Bold
       ↓
Apply changes
```

AI/computer vision works behind the scenes to reconstruct the image.

The actual editing experience is deterministic and user-controlled.

This makes the application closer to a combination of:

* Figma
* Canva
* Adobe Illustrator
* Photoshop

with an automated **image-to-editable-design import system**.

---

# 6. Image Processing Pipeline

The application will process an uploaded image through several stages.

## Stage 1 — Image Upload

The user uploads an image file.

Supported initial formats may include:

```text
PNG
JPG
JPEG
WEBP
```

The backend receives the image and begins analysis.

---

## Stage 2 — Image Analysis

The system analyzes the image to identify different types of visual content.

Potential categories include:

```text
Text
Shapes
Vectors
Logos
Icons
Photographs
Illustrations
Backgrounds
Gradients
Decorative elements
```

The system should also determine:

* Bounding boxes
* Position
* Size
* Rotation
* Dominant colors
* Layer relationships
* Transparency
* Object boundaries

---

# 7. Text Detection and Reconstruction

Text is treated as a special object because it should ideally remain editable as actual text rather than simply becoming vector outlines.

The system detects text regions using OCR and text-detection techniques.

For each detected text element, the system attempts to determine:

```text
Text content
Font family
Font weight
Font size
Text color
Letter spacing
Line height
Alignment
Rotation
Position
```

For example:

```json
{
  "type": "text",
  "content": "SUMMER SALE",
  "fontFamily": "Poppins",
  "fontSize": 64,
  "fontWeight": 700,
  "color": "#FFFFFF",
  "x": 240,
  "y": 120,
  "rotation": 0
}
```

If the original font cannot be confidently identified, the system may select the closest available font.

As a fallback, text can be converted into vector outlines so that its appearance is preserved even when true text reconstruction is not possible.

---

# 8. Shape Detection

Simple geometric elements can often be reconstructed with high accuracy.

Examples include:

```text
Rectangle
Circle
Ellipse
Line
Polygon
Rounded rectangle
```

Instead of storing these as pixels, the system reconstructs them as actual geometric objects.

For example:

```json
{
  "type": "circle",
  "x": 500,
  "y": 300,
  "radius": 120,
  "fill": "#FF5733"
}
```

This allows the user to:

* Resize the shape
* Change its color
* Change its border
* Change its opacity
* Rotate it
* Move it
* Duplicate it
* Delete it

without losing quality.

---

# 9. Vector Reconstruction

More complicated illustrations and logos can be converted into vector paths.

The system attempts to identify edges, boundaries, and regions and reconstruct them as SVG-like vector paths.

Instead of:

```text
Pixels
████████████████
████████████████
```

the resulting object becomes:

```text
Vector Path
M 100 200
L 200 100
L 300 200
Z
```

This allows the element to be resized without the pixelation associated with raster images.

The vector representation may not always match the original source artwork exactly, but the goal is to create a visually faithful and editable representation.

---

# 10. Image and Photograph Handling

Photographs are fundamentally different from vector graphics.

A photograph does not contain explicit editable layers.

Therefore, the application uses segmentation to identify meaningful regions where possible.

For example:

```text
Photograph
│
├── Person
├── Object
├── Background
└── Other regions
```

These regions can potentially become independent image layers or masked objects.

However, the application should clearly distinguish between:

**True reconstruction**

and

**Approximate segmentation.**

A flattened photograph cannot reliably be converted back into its original Photoshop layers because that original information was never stored in the image.

---

# 11. Editable Scene Graph

The most important internal representation of the project is the **scene graph**.

Rather than directly converting an image into one SVG file, the application creates a structured document describing every reconstructed element.

Example:

```json
{
  "canvas": {
    "width": 1920,
    "height": 1080
  },
  "layers": [
    {
      "id": "background",
      "type": "rectangle",
      "fill": "#FFFFFF"
    },
    {
      "id": "heading",
      "type": "text",
      "content": "SUMMER SALE",
      "fontFamily": "Poppins",
      "fontSize": 64,
      "color": "#111111",
      "x": 300,
      "y": 180
    },
    {
      "id": "circle",
      "type": "circle",
      "radius": 120,
      "fill": "#FF5733"
    },
    {
      "id": "product",
      "type": "image",
      "src": "/assets/product.png"
    }
  ]
}
```

The editor operates on this scene graph.

This allows every object to have its own properties and behavior.

---

# 12. Browser-Based Design Editor

After reconstruction, the user enters an interactive editor.

The editor should provide a familiar design-tool interface.

### Layers Panel

```text
Layers
──────────────
👁 Background
👁 Logo
👁 Heading
👁 Subtitle
👁 Circle
👁 Product
```

Users should be able to:

* Select layers
* Hide/show layers
* Reorder layers
* Lock layers
* Rename layers
* Delete layers
* Duplicate layers

---

# 13. Canvas

The central canvas displays the reconstructed design.

Users can interact with objects using standard manipulation controls.

Supported operations should include:

* Click to select
* Drag to move
* Resize
* Rotate
* Duplicate
* Delete
* Multi-select
* Group
* Ungroup
* Align
* Distribute

The editor should preserve the relationships between objects while allowing independent modifications.

---

# 14. Properties Panel

Selecting an object exposes its editable properties.

### Text

```text
Text
Font
Font size
Weight
Color
Alignment
Letter spacing
Line height
Opacity
Rotation
Position
```

### Shapes

```text
Fill
Stroke
Stroke width
Opacity
Corner radius
Position
Size
Rotation
```

### Images

```text
Width
Height
Position
Rotation
Opacity
Crop
Mask
Filters
```

### Vectors

```text
Fill
Stroke
Stroke width
Opacity
Transform
Path editing
```

---

# 15. Color Editing

One of the major goals is allowing users to change colors independently.

For example, an uploaded image might contain:

```text
Red circle
White text
Blue background
```

The reconstructed document stores these as independent properties.

The user can then change:

```text
Red → Green
Blue → Purple
White → Black
```

without modifying unrelated elements.

Color editing should support:

* HEX
* RGB
* HSL
* Opacity
* Gradients
* Stroke colors
* Fill colors

---

# 16. Typography Editing

Typography should remain as editable as possible.

Users should be able to modify:

* Text content
* Font family
* Font size
* Font weight
* Italic
* Alignment
* Letter spacing
* Line height
* Text color
* Text transform
* Rotation

For example:

```text
Original:

SUMMER SALE
Poppins
64px
White

↓

Modified:

WINTER SALE
Inter
80px
Black
```

---

# 17. Export System

After editing, users should be able to export the result.

Potential formats include:

```text
PNG
JPG
SVG
PDF
```

The application should also support saving the project in its own editable format.

For example:

```text
project.editable
```

containing:

```text
Scene Graph
+
Assets
+
Typography
+
Layer structure
+
Editor metadata
```

This allows users to reopen their project later and continue editing it.

---

# 18. Accuracy and Confidence

A major feature of the system should be transparency around reconstruction quality.

Not every image can be reconstructed perfectly.

The application can provide confidence information such as:

```text
Reconstruction
────────────────────
Text           98%
Shapes         97%
Logo           92%
Images         89%
Background     95%

Overall        94%
```

This helps users understand which elements are likely to be accurately editable and which may require manual correction.

---

# 19. Handling Difficult Images

The application should not pretend that every image can be perfectly reconstructed.

For example, a simple poster:

```text
Text
Shapes
Flat colors
Logo
```

may be reconstructed very accurately.

A highly complex photograph:

```text
Person
Hair
Glass
Reflections
Shadows
Textures
Lighting
Background
```

will be significantly harder.

Therefore, the system should use a **progressive reconstruction strategy**.

Simple elements receive high-confidence editable representations.

Complex elements receive approximate representations or remain raster-based where necessary.

---

# 20. Suggested Technology Stack

### Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
```

### Design Editor

One of:

```text
Fabric.js
Konva.js
SVG
```

A hybrid architecture can also be used.

### Backend

```text
Python
FastAPI
```

### Image Processing

```text
OpenCV
Pillow
NumPy
```

### OCR

Potential options:

```text
PaddleOCR
Tesseract
EasyOCR
```

### Computer Vision / Segmentation

Potentially:

```text
SAM / SAM 2
Object detection models
Image segmentation models
Edge detection
Contour detection
```

### Vectorization

Potential approaches:

```text
Potrace
OpenCV contours
Custom SVG path generation
```

### Database / Storage

```text
PostgreSQL
Supabase Storage
```

### Deployment

```text
Frontend → Vercel
Backend → Render / Railway / AWS
Storage → Supabase
```

---

# 21. High-Level Architecture

```text
                    USER
                     │
                     ▼
             ┌───────────────┐
             │   Next.js     │
             │   Web Editor  │
             └───────┬───────┘
                     │
                     │ Upload
                     ▼
             ┌───────────────┐
             │    FastAPI    │
             │    Backend    │
             └───────┬───────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       OCR       Segmentation  CV
          │          │          │
          └──────────┼──────────┘
                     ▼
             Reconstruction
                     │
                     ▼
              Scene Graph
                     │
                     ▼
             Editable Document
                     │
                     ▼
              Next.js Editor
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Edit       Save        Export
```

---

# 22. MVP Scope

The first version should **not** attempt to reconstruct every possible image.

The MVP should focus on graphic designs containing:

* Text
* Rectangles
* Circles
* Simple shapes
* Flat colors
* Logos
* Simple illustrations
* Basic images

The MVP pipeline should be:

```text
Upload PNG/JPG
       ↓
Detect text
       ↓
Detect basic shapes
       ↓
Extract colors
       ↓
Segment images
       ↓
Create scene graph
       ↓
Render editable canvas
       ↓
Allow manual editing
       ↓
Export
```

This provides a realistic first version while keeping the architecture extensible.

---

# 23. Future Features

Once the core system works, the application can evolve into a much more capable design platform.

Potential future features include:

### Advanced vector reconstruction

Convert complex illustrations into editable SVG paths.

### Better font identification

Identify the closest matching font from a large font database.

### Smart layer grouping

Automatically organize objects into groups such as:

```text
Header
Hero section
Product
Background
Decorations
```

### Background removal

Automatically separate foreground objects from backgrounds.

### Advanced image editing

Allow users to edit segmented photographic regions independently.

### Version history

Allow users to undo/redo and restore previous versions.

### Collaboration

Multiple users can edit the same design.

### Templates

Users can save reconstructed designs as reusable templates.

### Project sharing

Generate shareable editable design links.

### Batch processing

Allow users to upload multiple images and reconstruct them automatically.

---

# 24. What Makes This Project Interesting

The design editor itself is not the primary innovation.

The challenging component is:

**Recovering structure from flattened visual data.**

The project combines several areas of software engineering and computer science:

```text
Computer Vision
       +
OCR
       +
Image Processing
       +
Vector Graphics
       +
Frontend Engineering
       +
Interactive Editors
       +
Data Modeling
       +
File Processing
```

The result is a system that attempts to bridge the gap between:

**Raster graphics**

and

**structured editable designs.**

---

# 25. Final Product Vision

The long-term vision is to create a platform where a user can take almost any visual design they have access to and transform it into a structured editable document.

The experience should be:

```text
        ANY SUPPORTED IMAGE
                │
                ▼
          Upload
                │
                ▼
      Automatic Reconstruction
                │
                ▼
       ┌──────────────────┐
       │ Editable Design  │
       ├──────────────────┤
       │ Text             │
       │ Vectors          │
       │ Shapes           │
       │ Images           │
       │ Colors           │
       │ Layers           │
       └──────────────────┘
                │
                ▼
        USER EDITS MANUALLY
                │
                ▼
       Export / Save / Share
```

The core promise is simple:

> **Don't just edit the image. Recover the design behind the image.**

The application should make a flattened image behave as much as possible like its original editable source file, while clearly handling cases where the original structure cannot be perfectly recovered.
