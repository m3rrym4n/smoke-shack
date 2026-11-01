# Smoke-Shack UI design reference: "BBQ joint signage"

Source: mockup #4 (Signage.dc.html, sample data only). Replicate the look in real components. Do not copy the mockup's runtime. Mobile first: every row wraps, tap targets are at least 44px.

## Fonts (Google Fonts)
Rye (sign lettering, buttons, gauge numerals), Bungee (neon sign), Caveat Brush (headings, big numbers), Patrick Hand (body, default).

## Palette
- Page wood: #4a2d19 (dark planks: vertical 3px lines every 150px, plus a top shade)
- Chalkboard panel (.board): #1f2b25, border 16px solid #7a4a24, radius 8px, inner shadow, text #f1efe4
- Chalk yellow (headings, accents, active): #f7d65a
- Chalk salmon (pit temp, danger text): #f4a38a
- Chalk blue (probe line): #9fd3e6
- Chalk green (plugged in): #a8d8a0
- Muted chalk (.mut): #b9c3b5
- Sign red: #a3231a (shadow #5e130e), cream: #f6ead0 / #f1e3c0, ink: #17110c / #2a1b10
- Neon pink: #ff6fb5 / #ff2e97 / #ffd6ec on #1a0f16
- Paper (notes, order pad): #f6efdc, ink #23232e, pen blue #3b4a8a, muted brown #6a5640

## Core CSS (from the mockup helmet; use as-is)
```css
body{margin:0}
button{font-family:inherit;cursor:pointer}
input,textarea{font-family:inherit}
@keyframes flick{0%,18%,22%,60%,100%{opacity:1}20%,62%{opacity:.78}}
.neon{animation:flick 5s linear infinite}
.board{position:relative;background-color:#1f2b25;background-image:radial-gradient(ellipse at 28% 18%,rgba(255,255,255,.08),rgba(255,255,255,0) 60%),radial-gradient(ellipse at 82% 92%,rgba(255,255,255,.06),rgba(255,255,255,0) 55%);border:16px solid #7a4a24;border-radius:8px;box-shadow:inset 0 0 0 3px #4a2d19,inset 0 0 50px rgba(0,0,0,.65),0 10px 0 rgba(0,0,0,.35);color:#f1efe4;font-family:'Patrick Hand',cursive;font-size:19px;min-width:0}
.hd{margin:0;font-family:'Caveat Brush',cursive;font-weight:400;font-size:42px;color:#f7d65a;line-height:1}
.cc{border:2.5px solid rgba(241,239,228,.85);border-radius:22px 18px 24px 16px;padding:8px 16px;min-height:44px;box-sizing:border-box;background:transparent;color:#f1efe4;font-family:'Patrick Hand',cursive;font-size:18px}
.cc.on{border-color:#f7d65a;color:#f7d65a;background:rgba(247,214,90,.16)}
.pbtn{font-family:'Rye',serif;font-size:17px;border:3px solid #f1e3c0;box-shadow:0 0 0 3px #1a110a,0 5px 0 3px #1a110a;border-radius:8px;min-height:48px;display:flex;align-items:center;justify-content:center;gap:8px}
.pbtn:active{transform:translateY(3px)}
.ld{display:flex;align-items:baseline;gap:10px}
.ld i{flex:1;border-bottom:3px dotted rgba(241,239,228,.55)}
.mut{color:#b9c3b5}
.lb{font-size:14px;letter-spacing:.1em;text-transform:uppercase;color:#b9c3b5}
.ci{background:rgba(255,255,255,.06);border:2px solid rgba(241,239,228,.6);border-radius:12px 10px 14px 10px;color:#f1efe4;font-family:'Patrick Hand',cursive;font-size:20px;min-height:44px;padding:6px 12px;box-sizing:border-box;width:100%}
.ci::placeholder{color:#9fab9c}
.fl{display:flex;flex-direction:column;gap:4px;min-width:0}
.rb{width:44px;height:44px;border-radius:50%;border:2.5px solid rgba(241,239,228,.85);background:transparent;color:#f1efe4;font-family:'Caveat Brush',cursive;font-size:30px}
.val{font-family:'Caveat Brush',cursive;font-size:36px;min-width:88px;text-align:center}
.seg{display:flex;border:2.5px solid rgba(241,239,228,.85);border-radius:22px 18px 24px 16px;overflow:hidden}
.seg button{background:transparent;border:0;color:#f1efe4;font-size:18px;min-height:44px;padding:0 14px}
.seg button.on{background:rgba(247,214,90,.2);color:#f7d65a}
.num{width:44px;height:44px;border-radius:50%;border:3px solid #f7d65a;color:#f7d65a;font-family:'Caveat Brush',cursive;font-size:30px;display:flex;align-items:center;justify-content:center}
.ib{width:44px;height:44px;border-radius:50%;border:2px solid rgba(241,239,228,.6);background:transparent;display:flex;align-items:center;justify-content:center}
.stp{border:3px solid rgba(241,239,228,.75);border-radius:16px 12px 18px 12px;padding:16px;display:flex;flex-direction:column;gap:14px;background:rgba(255,255,255,.03)}
.pin{width:34px;height:34px;border-radius:50%;background:#f7d65a;color:#1f2b25;font-family:'Caveat Brush',cursive;font-size:24px;display:flex;align-items:center;justify-content:center}
.pin.auto{background:transparent;border:2px solid #b9c3b5;color:#b9c3b5}
.ev{display:flex;gap:14px;padding:12px 0;border-top:2px dotted rgba(241,239,228,.35);align-items:flex-start}
.note{position:relative;background:#f6efdc;color:#23232e;border-radius:4px;box-shadow:0 6px 0 rgba(0,0,0,.35);padding:22px 18px 16px;display:flex;flex-direction:column;gap:8px;min-width:0}
.tape{position:absolute;width:70px;height:22px;background:rgba(247,214,90,.7);border:1px solid rgba(0,0,0,.15);left:50%;margin-left:-35px;top:-11px}
```

## Page layout (max-width 1200px, padding 30px 24px, gap 36px)
1. Header signs: red SMOKE-SHACK sign (Rye 46px, cream text, 5px cream border + 5px dark outer ring, rotate -1deg, subtitle "PELLET-FIRED · LOW & SLOW" 18px letter-spacing .2em) and a pink neon "NOW SMOKING" sign (Bungee 26px, rotate 1.5deg, `.neon`). The neon sign shows only while a cook is active.
2. Nav row of `.pbtn` links: Today's special (active, cream bg #f1e3c0, ink text) / Cook log / Profiles / Pellets / Meat / Notes / Ask the pitmaster (inactive: bg #6b3f1f, text #f1e3c0).
3. Hero (flex-wrap, gap 36): left board "The Pit" with a round gauge, setpoint chips (225/250/275/350/450 as `.cc`), and Start/Fan/Shutdown `.pbtn` (red / cream / dark). Right column: "Today's Special" board and probe boards.
   - Gauge: SVG 400x400. Black rim, red ring, cream face; ticks every 10 degrees (small) and 50 (large); numerals 0 to 500 in Rye; center text "SMOKE-SHACK" (red, 17px), the big temp (Rye 52px), "DEGREES F"; amber setpoint marker triangle at the rim; red needle with hub; "SETPOINT 275" below.
   - Today's Special: Caveat Brush 46px heading, meat name 38px with weight in salmon, a muted line (setpoint, pellets, profile), a phase bar (28px tall, 3px chalk border; startup = yellow fill, cook = salmon diagonal stripes, remaining = empty; flex proportions by duration), and `.ld` rows for Startup / Cook (yellow, 24px while active) / Cool down / Total grill time (double top rule).
   - Probe board: label, "plugged in" green pill, big temp (Caveat Brush 78px salmon), "aiming for N", progress bar (SVG pill outline with salmon fill, tick marks), "N% of the way to done". Unplugged probe board: X icon plus "sold out (unplugged)" in muted chalk.
4. "Chalked up: this cook" board: SVG line chart on a 1100x316 canvas. Pit line salmon 5px, probe line blue 5px, dashed cream target line labeled "done at N", startup band as translucent yellow rectangle, a chalk displacement filter (feTurbulence 0.9, scale 2.5) on lines, and numbered yellow event pins on dotted vertical lines. Legend row above. Horizontal scroll on phones (min-width 700px).
5. Cook Log board: `.ev` rows, with a numbered `.pin` for user events and an icon `.pin.auto` for system events (fire lit, setpoint changes). Title in Caveat Brush 28px, yellow for user events. Meta line: date, clock time, time into the cook, "auto" for system events. Edit button `.ib` on user events. Beside it, the "Pin an event" board: quick chips (Stall, Wrapped, Spritzed, Sauced, Flipped, Rested, Custom), title, When (right now / pick date and time) `.seg`, what happened textarea, "Pin it" (yellow `.pbtn`), "Add photo".
6. Profiles board: list of profiles as `.cc` buttons on the left; editor on the right with the name, step cards (`.stp`: number `.num`, grill temp stepper with `.rb` and `.val`, Stop at Time/Internal temp `.seg`, minutes or probe/target, reorder and delete `.ib`, instructions), "Add a step" dashed button, keep-warm toggle (68x36 switch) with hold temp, "Shape of the cook" SVG, Save profile and Start profile.
7. The Butcher Case: list of cuts (name, store and date, lbs, $/lb in yellow, total, edit and delete) plus an "Add a cut" `.stp` form.
8. The Pellet Pantry: vendor and product, $/lb, "used in N cooks", edit and delete, plus an "Add a pellet" form.
9. Pit Notes: scope filter chips (All / This cook / Pellets / Gear), a quick-add row, and sticky `.note` cards with tape, slight rotations (-1 to 1deg), title, body, scope and date footer.
10. Ask the Pitmaster: filter chips (meat, weight, setpoint, rotisserie), a big answer line ("4 lb Picnic Shoulder @ 275° ..... 6h 12m", Caveat Brush, answer 60px yellow), a stats line (average cook phase, matching cooks, fastest, slowest), a dot strip (blue dots by duration, yellow bar = average), and a list of the matching cooks as `.ld` rows. Beside it, the "ORDER PAD" paper form (red Rye header, "No. 0042", ruled-paper background; fields Meat, Weight, Seasonings, Sauces, Prep time, Pellets, Profile used, Rotisserie Yes/No, How it turned out, photo drop) used to start or log a cook.

## Notes for implementation
- All data in the mockup is sample data. Real data comes from the API.
- Times show date, clock time and time into the cook.
- Temps are Fahrenheit.
- Keep controls reachable on a phone beside the grill: big targets, no hover-only affordances.
