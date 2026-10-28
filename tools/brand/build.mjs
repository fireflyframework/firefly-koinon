// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {openSync} from 'fontkit';
import {Resvg} from '@resvg/resvg-js';
const here=dirname(fileURLToPath(import.meta.url)),root=resolve(here,'../..');
const font=openSync(resolve(here,'node_modules/@fontsource/manrope/files/manrope-latin-500-normal.woff'));
const palette=JSON.parse(readFileSync(resolve(root,'brand/tokens.json'),'utf8')).palette;
const svg=(box,body,title)=>`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}"><title>${title}</title>${body}</svg>`;
function koinonO(ink,accent){
 return `<path fill="${ink}" d="M600 1110C272 1110 80 904 80 540S272 -30 600 -30 1121 176 1121 540V646H943V540C943 280 824 148 600 148S258 280 258 540 376 932 600 932H752V1110Z"/><path fill="${accent}" d="M790 1100C1002 1050 1121 898 1121 690H943C943 818 886 897 790 922Z"/>`;
}
function type(text,x,y,size,ink,accent=ink){
 const run=font.layout(text);let advance=0;
 const paths=run.glyphs.map((glyph,i)=>{const form=text==='koinon'&&i===1?koinonO(ink,accent):`<path d="${glyph.path.toSVG()}"/>`;const path=`<g transform="translate(${advance} 0)">${form}</g>`;advance+=run.positions[i].xAdvance;return path;}).join('');
 return {body:`<g fill="${ink}" transform="translate(${x} ${y}) scale(${size/font.unitsPerEm} ${-size/font.unitsPerEm})">${paths}</g>`,width:advance*size/font.unitsPerEm};
}
let markId=0;
function mark(ink,accent){
 const id=`koinon-${++markId}`;
 const first='M34 12H44C58 12 68 22 68 36V44C68 58 58 68 44 68H34C20 68 10 58 10 44V36C10 22 20 12 34 12Z';
 const second='M52 28H62C76 28 86 38 86 52V60C86 74 76 84 62 84H52C38 84 28 74 28 60V52C28 38 38 28 52 28Z';
 const joint='M44 12C58 12 68 22 68 36V46';
 return `<defs><mask id="${id}-a"><rect width="96" height="96" fill="white"/><path d="${second}" fill="none" stroke="black" stroke-width="18"/></mask><mask id="${id}-b"><rect width="96" height="96" fill="white"/><path d="${joint}" fill="none" stroke="black" stroke-width="18"/></mask></defs><g fill="none" stroke-width="12" stroke-linecap="butt" stroke-linejoin="round"><path d="${first}" stroke="${ink}" mask="url(#${id}-a)"/><path d="${second}" stroke="${ink}" mask="url(#${id}-b)"/><path d="${joint}" stroke="${accent}"/></g>`;
}

function nested(source,x,y,width){
 const box=source.match(/viewBox="([^"]+)"/)[1].split(' ').map(Number);
 return source.replace('<svg ',`<svg x="${x}" y="${y}" width="${width}" height="${width*box[3]/box[2]}" `);
}
const variants=[['color',palette.charcoal,palette.amber],['reversed',palette.paper,palette.amber],['mono-black',palette.charcoal,palette.charcoal],['mono-white',palette.white,palette.white]];
const assets=[];
function save(path,body){
 if(path.endsWith('.svg')||path.endsWith('.html'))body='<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->\n'+body;
 writeFileSync(resolve(root,path),body);assets.push(path);
}
for(const [name,ink,accent] of variants){
 const symbol=svg('0 0 96 96',mark(ink,accent),'koinon common-ground mark');
 save(`brand/logos/koinon-symbol-${name}.svg`,symbol);
 const word=type('koinon',112,78,76,ink,accent);
 const wordmark=svg(`0 0 ${word.width+124} 100`,mark(ink,accent)+word.body,'koinon');
 save(`brand/logos/koinon-wordmark-${name}.svg`,wordmark);
 const parent=readFileSync(resolve(root,`brand/source/firefly-${name}.svg`),'utf8');
 const end=type('koinon',300,76,72,ink,accent);
 const lockup=svg(`0 0 ${end.width+312} 104`,nested(parent,8,27,206)+`<path d="M245 20V86" stroke="${ink}" stroke-opacity=".35" stroke-width="1.5"/>`+end.body,'firefly | koinon');
 save(`brand/logos/firefly-koinon-lockup-${name}.svg`,lockup);
 for(const size of [16,24,32,64,128,256,512])save(`brand/exports/koinon-symbol-${name}-${size}.png`,new Resvg(symbol,{fitTo:{mode:'width',value:size}}).render().asPng());
 save(`brand/exports/firefly-koinon-lockup-${name}-1600.png`,new Resvg(lockup,{fitTo:{mode:'width',value:1600}}).render().asPng());
}
const ink=palette.paper;
const lockup=readFileSync(resolve(root,'brand/logos/firefly-koinon-lockup-reversed.svg'),'utf8');
const title=type('Knowledge, together.',96,330,74,ink);
const subtitle=type('Tables, documents and the evidence that connects them.',100,398,25,palette.stone);
const banner=svg('0 0 1600 600',`<rect width="1600" height="600" fill="${palette.charcoal}"/>`+
 nested(lockup,98,76,470)+title.body+subtitle.body+
 `<g transform="translate(1100 130) scale(3.8)">${mark(palette.paper,palette.amber)}</g>`+
 '','firefly koinon repository banner');
save('brand/repository-banner.svg',banner);
save('brand/exports/repository-banner.png',new Resvg(banner,{fitTo:{mode:'width',value:1600}}).render().asPng());
const rows=variants.map(([name])=>`<article><div class="sample ${name.includes('white')||name==='reversed'?'dark':''}"><img src="logos/firefly-koinon-lockup-${name}.svg" alt="firefly koinon ${name} lockup"/></div><p>${name.replaceAll('-',' ')}<a href="logos/firefly-koinon-lockup-${name}.svg" download>SVG</a></p></article>`).join('');
const page=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>firefly koinon identity</title><style>@font-face{font-family:Manrope;src:url(fonts/manrope-latin-500-normal.woff2)}*{box-sizing:border-box}body{margin:0;background:#f3f1eb;color:#272820;font:16px/1.65 Manrope,Arial,sans-serif}main{max-width:1440px;padding:64px 48px;margin:auto}h1{font-size:clamp(40px,6vw,76px);font-weight:500;line-height:1.08;letter-spacing:-.055em;max-width:900px}h2{font-size:28px;font-weight:500;letter-spacing:-.035em;margin:64px 0 20px}.lead{max-width:750px;font-size:20px}.banner{width:100%;margin:32px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.sample{background:white;height:220px;display:flex;align-items:center;padding:40px}.dark{background:#10110f}.sample img{width:100%;height:auto}article p{display:flex;justify-content:space-between;margin:12px 0}a{color:inherit;text-underline-offset:4px}.swatches{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}.swatch{height:100px;border:1px solid #d8d4ca}.small{max-width:800px;color:#62645b}code{background:#e4e1d9;padding:2px 6px}.heart{display:inline-block;width:14px;height:14px;vertical-align:-2px;fill:currentColor;transform-origin:center;animation:heartbeat 2s ease-in-out infinite}@keyframes heartbeat{0%,28%,100%{transform:scale(1)}8%,20%{transform:scale(1.16)}14%{transform:scale(1)}}@media(prefers-reduced-motion:reduce){.heart{animation:none}}footer{margin-top:64px;padding-top:24px;border-top:1px solid #d8d4ca;font-size:13px}@media(max-width:650px){main{padding:32px 20px}.grid{grid-template-columns:1fr}.sample{height:160px;padding:24px}.swatches{grid-template-columns:repeat(2,1fr)}}a:focus-visible{outline:3px solid #855414;outline-offset:4px}</style><main><img src="logos/firefly-koinon-lockup-color.svg" width="340" alt="firefly koinon"><h1>Shared knowledge.<br>Clear provenance.</h1><p class="lead">Koinon gives tables, documents and evidence a common home. Its two letter-inspired loops meet through one highlighted link: connected knowledge that retains the identity of its sources.</p><img class="banner" src="repository-banner.svg" alt="Knowledge, together. Product banner"><h2>A Firefly product</h2><p class="small">Use the canonical firefly wordmark, its chevron, a quiet divider and the koinon wordmark. The product symbol stands alone for application icons and compact navigation. Parent geometry remains unchanged.</p><div class="grid">${rows}</div><h2>One geometric language</h2><div class="grid"><div class="sample"><img style="max-width:130px;margin:auto" src="logos/koinon-symbol-color.svg" alt="Koinon symbol"></div><div><p>Two loops derived from the two o letters in koinon interlock around a shared context. Their common joint carries the Firefly amber. The first o in the wordmark repeats that joint, giving the name its own recognizable detail. Curves, stroke weight and optical spacing follow the same drawing system.</p><p>Minimum symbol size: 16px. Clear space: one bridge width on every side. Do not distort, add shadows, replace the parent logo or recolor individual letters.</p></div></div><h2>Framework colors</h2><div class="swatches">${['charcoal','paper','amber','ink','muted'].map(key=>`<div><div class="swatch" style="background:${palette[key]}"></div>${key}<br><code>${palette[key]}</code></div>`).join('')}</div><h2>Manrope, with a purpose</h2><p class="lead">Knowledge, together.</p><p class="small">Use Manrope 400 for reading, 500 for titles and 600–700 for controls. Keep body text at 16px with generous line height. Use amber for the primary action and active evidence, gold for amber-family text on light surfaces. Layout and theme values come from <a href="tokens.json">versioned tokens</a>.</p><h2>Editable and reproducible</h2><p class="small">SVG files use outlined Manrope for reliable logos. Application typography uses licensed font files. Rebuild symbols, lockups, banners and PNG exports with <code>npm ci --prefix tools/brand</code> then <code>npm run build --prefix tools/brand</code>. See <a href="NOTICE.md">brand notice</a> and <a href="OFL.txt">font license</a>.</p><footer>© 2026 Firefly Software Foundation · Made with <svg class="heart" viewBox="0 0 24 24" role="img" aria-label="love"><path d="M12 21 3.6 12.7C-2 7.1 5.3-.8 12 5.3 18.7-.8 26 7.1 20.4 12.7Z"/></svg> · Apache-2.0</footer></main></html>`;
save('brand/index.html',page);
const lightLockup=readFileSync(resolve(root,'brand/logos/firefly-koinon-lockup-color.svg'),'utf8');
const darkLockup=readFileSync(resolve(root,'brand/logos/firefly-koinon-lockup-reversed.svg'),'utf8');
const identityPreview=svg('0 0 1600 1000',`<rect width="1600" height="500" fill="${palette.paper}"/><rect y="500" width="1600" height="500" fill="${palette.charcoal}"/>`+
 nested(lightLockup,80,142,1000)+`<g transform="translate(1210 116) scale(2.6)">${mark(palette.charcoal,palette.amber)}</g>`+
 type('Two sources. One shared context.',88,390,34,palette.muted).body+
 nested(darkLockup,80,642,1000)+`<g transform="translate(1210 616) scale(2.6)">${mark(palette.paper,palette.amber)}</g>`+
 type('A shared joint in the first o. Two linked o forms in the symbol.',88,890,28,palette.stone).body,'firefly koinon refined identity');
save('brand/exports/identity-preview.png',new Resvg(identityPreview,{fitTo:{mode:'width',value:1600}}).render().asPng());
save('brand/source/koinon-o-master.svg',svg('0 0 1201 1200',`<g transform="translate(0 1140) scale(1 -1)">${koinonO(palette.charcoal,palette.amber)}</g>`,'koinon custom first o'));

writeFileSync(resolve(root,'brand/assets.json'),JSON.stringify({version:'1.2.0',assets},null,2)+'\n');
console.log(`Built ${assets.length} identity assets.`);
