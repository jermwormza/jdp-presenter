# JDP Presenter service-file generation instructions

You are generating a valid JDP Presenter service JSON file for the app.

This project stores each service as a JSON document shaped like the app's `Service` model. Output only valid JSON, no explanation, no markdown fences, no extra text outside the JSON object.

## Required output format

The top-level object must look like this:

{
  "id": "service-2026-09-27",
  "version": "1.0",
  "name": "Sunday Morning Service",
  "date": "2026-09-27",
  "theme": {
    "background": {
      "type": "color",
      "color": "#000000",
      "opacity": 1.0
    },
    "scripture": {
      "verseText": {
        "fontFamily": "Inter",
        "fontSize": 48,
        "fontWeight": "normal",
        "fontStyle": "normal",
        "color": "#ffffff",
        "textAlign": "left"
      },
      "reference": {
        "fontFamily": "Inter",
        "fontSize": 32,
        "fontWeight": "bold",
        "fontStyle": "normal",
        "color": "#22d3ee",
        "textAlign": "left",
        "position": "bottom-right"
      },
      "version": {
        "fontFamily": "Inter",
        "fontSize": 24,
        "fontWeight": "normal",
        "fontStyle": "italic",
        "color": "#94a3b8",
        "textAlign": "left",
        "show": true,
        "position": "bottom-left"
      },
      "verseLineBreaks": false
    },
    "song": {
      "lyrics": {
        "fontFamily": "Inter",
        "fontSize": 56,
        "fontWeight": "bold",
        "fontStyle": "normal",
        "color": "#ffffff",
        "textAlign": "left"
      },
      "metadata": {
        "fontFamily": "Inter",
        "fontSize": 24,
        "fontWeight": "normal",
        "fontStyle": "normal",
        "color": "#94a3b8",
        "textAlign": "left",
        "show": true,
        "position": "bottom-left"
      }
    }
  },
  "items": [],
  "createdAt": "2026-09-27T00:00:00Z",
  "updatedAt": "2026-09-27T00:00:00Z"
}

## Item rules

Each item in `items` must be an object with:
- `id`: unique string
- `type`: one of `scripture`, `song`, `text`, `image`, `video`, `audio`, `pdf`, `pptx`
- `title`: visible item label
- `slides`: array of slide objects
- optional `displaySettings`

### 1) Scripture item
Use this for Bible readings.

Required fields:
- `type`: "scripture"
- `bible`: bible version name, for example "KJV", "ESV", "NIV", "WEB", etc.
- `reference`: short reference like "Psalm 23" or "John 1:1-5"
- `verses`: array of objects with `book`, `chapter`, `verse`, `text`

Example:
{
  "id": "scripture-1",
  "type": "scripture",
  "title": "Opening Reading",
  "bible": "KJV",
  "reference": "Psalm 23",
  "verses": [
    { "book": "Psalm", "chapter": 23, "verse": 1, "text": "The LORD is my shepherd; I shall not want." },
    { "book": "Psalm", "chapter": 23, "verse": 2, "text": "He maketh me to lie down in green pastures:" }
  ],
  "slides": [],
  "displaySettings": null
}

### 2) Song item
Use this for songs with lyrics from the library.

Required fields:
- `type`: "song"
- `songId`: exact song id from the library
- `selectedVerses`: array of lyrics verse labels/sections to include; if you do not know the exact library structure, use the verse labels that match the song's content order (for example ["Verse 1", "Chorus", "Verse 2", "Chorus"])
- `slides`: array of slide objects; each slide has `id`, `content`, `label`

Example:
{
  "id": "song-1",
  "type": "song",
  "title": "Amazing Grace",
  "songId": "amazing-grace",
  "selectedVerses": ["Verse 1", "Chorus", "Verse 2", "Chorus"],
  "slides": [
    { "id": "song-1-slide-1", "label": "Verse 1", "content": "Amazing grace, how sweet the sound\nThat saved a wretch like me" },
    { "id": "song-1-slide-2", "label": "Chorus", "content": "I once was lost, but now am found\nWas blind, but now I see" }
  ],
  "displaySettings": null
}

### 3) Text item
Use this for announcements, intro text, prayers, or short spoken text.

Example:
{
  "id": "text-1",
  "type": "text",
  "title": "Announcements",
  "content": "Please welcome our visitors and keep the prayer team in your thoughts.",
  "slides": [],
  "displaySettings": null
}

### 4) Image / video / audio / pdf / pptx
Use these only if you have actual file paths and the item should be displayed or played. Include `path` as appropriate.

Example image item:
{
  "id": "image-1",
  "type": "image",
  "title": "Church Banner",
  "path": "/media/church-banner.jpg",
  "fit": "contain",
  "scaleMode": "fit",
  "slides": [],
  "displaySettings": null
}

## Important constraints

- Always produce valid JSON, not pseudo-JSON.
- Do not include comments.
- Use double quotes for all keys and string values.
- Keep `theme` as shown above unless you purposely want a different style.
- If the service is built from an order of service, preserve the order exactly in the `items` array.
- For scripture items, the app expects the verse text as plain strings in each `verses` object; verse numbers are part of the object fields.
- For song items, the app expects the song library id in `songId` and the lyric content in `slides`.
- If you do not know the exact `songId`, use a realistic library id that matches the song title and keep the item consistent.
- If you do not know a specific bible version, default to `KJV` unless the request says otherwise.

## Generation behavior

Build a service file from the order of service in natural order. Example sequence:
1. Opening prayer / welcome text
2. Scripture reading
3. Song
4. Sermon / text or image slide
5. Another song
6. Closing prayer / final text

The `items` array should match the actual order as presented in the service.

## Example full service

{
  "id": "service-sunday-2026-09-27",
  "version": "1.0",
  "name": "Sunday Morning Service",
  "date": "2026-09-27",
  "theme": {
    "background": { "type": "color", "color": "#000000", "opacity": 1.0 },
    "scripture": {
      "verseText": { "fontFamily": "Inter", "fontSize": 48, "fontWeight": "normal", "fontStyle": "normal", "color": "#ffffff", "textAlign": "left" },
      "reference": { "fontFamily": "Inter", "fontSize": 32, "fontWeight": "bold", "fontStyle": "normal", "color": "#22d3ee", "textAlign": "left", "position": "bottom-right" },
      "version": { "fontFamily": "Inter", "fontSize": 24, "fontWeight": "normal", "fontStyle": "italic", "color": "#94a3b8", "textAlign": "left", "show": true, "position": "bottom-left" },
      "verseLineBreaks": false
    },
    "song": {
      "lyrics": { "fontFamily": "Inter", "fontSize": 56, "fontWeight": "bold", "fontStyle": "normal", "color": "#ffffff", "textAlign": "left" },
      "metadata": { "fontFamily": "Inter", "fontSize": 24, "fontWeight": "normal", "fontStyle": "normal", "color": "#94a3b8", "textAlign": "left", "show": true, "position": "bottom-left" }
    }
  },
  "items": [
    {
      "id": "text-1",
      "type": "text",
      "title": "Welcome",
      "content": "Good morning church, thank you for gathering together this morning.",
      "slides": [],
      "displaySettings": null
    },
    {
      "id": "scripture-1",
      "type": "scripture",
      "title": "Opening Reading",
      "bible": "KJV",
      "reference": "Psalm 23",
      "verses": [
        { "book": "Psalm", "chapter": 23, "verse": 1, "text": "The LORD is my shepherd; I shall not want." },
        { "book": "Psalm", "chapter": 23, "verse": 2, "text": "He maketh me to lie down in green pastures:" }
      ],
      "slides": [],
      "displaySettings": null
    },
    {
      "id": "song-1",
      "type": "song",
      "title": "Amazing Grace",
      "songId": "amazing-grace",
      "selectedVerses": ["Verse 1", "Chorus"],
      "slides": [
        { "id": "song-1-slide-1", "label": "Verse 1", "content": "Amazing grace, how sweet the sound\nThat saved a wretch like me" },
        { "id": "song-1-slide-2", "label": "Chorus", "content": "I once was lost, but now am found\nWas blind, but now I see" }
      ],
      "displaySettings": null
    }
  ],
  "createdAt": "2026-09-27T00:00:00Z",
  "updatedAt": "2026-09-27T00:00:00Z"
}

## Final instruction

Generate the JSON service file based on the user’s order of service using this schema exactly. Keep the item order faithful to the service order. Use bible versions and song library records if known; otherwise default to KJV and realistic song IDs.
