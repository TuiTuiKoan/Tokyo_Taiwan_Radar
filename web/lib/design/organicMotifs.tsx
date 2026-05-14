import React from 'react';

// Generates one of 5 distinct semantic symbols per category
export function getSemanticSymbol(cat: string, variant: number, c: string, a: string): React.ReactNode {
  const v = variant % 5;
  switch (cat) {
    case 'performing_arts':
      if (v===0) return <g><path d="M40 30 Q50 20 70 30 L70 60 Q50 70 40 60 Z" fill={c}/><circle cx="55" cy="45" r="8" fill={a}/><path d="M40 30 L40 70" stroke="#3A261F" strokeWidth="4"/></g>; // horn
      if (v===1) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><rect x="40" y="30" width="8" height="25" fill="#3A261F"/><rect x="55" y="30" width="8" height="25" fill="#3A261F"/></g>; // piano
      if (v===2) return <g><polygon points="30,20 40,20 40,70 30,70" fill="#3A261F"/><polygon points="40,25 80,15 80,35 40,45" fill={a}/><ellipse cx="25" cy="75" rx="15" ry="10" transform="rotate(-15 25 75)" fill={c}/><ellipse cx="65" cy="80" rx="15" ry="10" transform="rotate(-15 65 80)" fill={a}/></g>; // notes
      if (v===3) return <g><circle cx="35" cy="30" r="6" fill={a}/><circle cx="65" cy="40" r="6" fill={a}/><path d="M35 40 Q45 60 30 80 M65 50 Q55 70 70 80 M20 50 Q30 45 40 50 M80 30 Q70 40 60 50" stroke={c} strokeWidth="6" strokeLinecap="round" fill="none"/></g>; // dancing figures
      if (v===4) return <g><path d="M30 60 Q20 40 40 30 Q50 20 60 30 Q80 40 70 60 T50 80 T30 60Z" fill={c}/><circle cx="45" cy="45" r="4" fill={a}/><circle cx="55" cy="45" r="4" fill={a}/></g>; // mask
    case 'movie':
      if (v===0) return <g><polygon points="20,40 25,35 75,45 80,90 20,85" fill="#3A261F"/><polygon points="20,35 80,25 83,40 23,50" fill={a}/><polygon points="30,50 70,55 70,80 30,75" fill={c}/></g>; // clapper
      if (v===1) return <g><path d="M20 30 L80 30 L80 70 L20 70 Z M30 40 L70 40 L70 60 L30 60 Z" fill={c}/><rect x="25" y="32" width="5" height="5" fill={a}/><rect x="70" y="32" width="5" height="5" fill={a}/></g>; // film frame
      if (v===2) return <g><rect x="25" y="45" width="50" height="30" fill={c}/><circle cx="35" cy="35" r="12" fill={a}/><circle cx="65" cy="35" r="12" fill={a}/><polygon points="75,50 90,40 90,70 75,60" fill="#3A261F"/></g>; // classic camera
      if (v===3) return <g><polygon points="20,20 40,25 35,50 25,50" fill={a}/><polygon points="60,20 80,25 75,50 65,50" fill={a}/><rect x="25" y="50" width="50" height="15" fill={c}/><path d="M30 65 L20 90 M70 65 L80 90 M30 80 L70 80" stroke="#3A261F" strokeWidth="4"/></g>; // director chair
      if (v===4) return <g><polygon points="10,50 90,20 90,80" fill={a} opacity="0.6"/><rect x="5" y="40" width="20" height="20" fill={c}/><circle cx="15" cy="50" r="5" fill="#3A261F"/></g>; // projector beam
    case 'art':
      if (v===0) return <g><path d="M20 50 C20 20 80 20 80 50 C80 80 60 90 40 80 C20 70 20 50 20 50 Z" fill={c}/><circle cx="40" cy="40" r="6" fill="#fff"/><circle cx="55" cy="35" r="6" fill={a}/></g>; // palette
      if (v===1) return <g><polygon points="20,20 80,20 70,30 30,30" fill={c}/><polygon points="20,20 30,30 30,80 20,80" fill={a}/><polygon points="80,20 80,80 70,80 70,30" fill={a}/><polygon points="20,80 80,80 70,70 30,70" fill={c}/></g>; // frame
      if (v===2) return <g><path d="M10 90 Q40 50 70 30 T90 10" stroke={c} strokeWidth="15" strokeLinecap="round" fill="none"/><circle cx="80" cy="50" r="8" fill={a}/><circle cx="70" cy="70" r="5" fill={a}/></g>; // brush stroke
      if (v===3) return <g><path d="M50 20 L30 50 Q30 70 60 80 L80 60 Z" fill={c}/><path d="M40 40 L50 60 L60 50" stroke={a} strokeWidth="4" fill="none"/></g>; // abstract bust
      if (v===4) return <g><path d="M70 90 Q65 60 85 45 Q60 40 60 20 Q50 40 30 35 Q45 60 20 80 Q40 80 70 90 Z" fill={a} opacity={0.8}/><polygon points="25,45 75,40 80,60 20,65" fill="#FFF"/><polygon points="35,30 65,25 65,35 35,40" fill={c}/></g>; // dada eye
    case 'nature':
      if (v===0) return <g><path d="M50 80 Q30 50 20 20 Q50 30 50 50 Q70 30 80 20 Q60 50 50 80 Z" fill={c}/><path d="M50 80 Q40 60 30 50 M50 80 Q60 60 70 50" stroke={a} strokeWidth="3" fill="none"/></g>; // fern
      if (v===1) return <g><path d="M10 90 L50 30 L70 60 L100 90 Z" fill={c}/><path d="M40 90 L70 40 L90 90 Z" fill={a} opacity={0.8}/></g>; // mountains
      if (v===2) return <g><circle cx="50" cy="40" r="20" fill={a}/><path d="M20 70 Q35 50 50 70 T80 70" stroke={c} strokeWidth="8" fill="none"/><path d="M20 85 Q35 65 50 85 T80 85" stroke={c} strokeWidth="8" fill="none"/></g>; // waves & sun
      if (v===3) return <g><path d="M40 90 L45 50 L55 50 L60 90 Z" fill="#3A261F"/><circle cx="35" cy="45" r="20" fill={c}/><circle cx="65" cy="45" r="20" fill={a}/><circle cx="50" cy="25" r="25" fill={c}/></g>; // tree canopy
      if (v===4) return <g><path d="M20 50 Q50 10 80 50 Q60 60 50 50 Q40 60 20 50 Z" fill={c}/><path d="M45 50 L40 80 L60 80 L55 50" fill={a}/></g>; // mushroom
    case 'senses':
      if (v===0) return <g><circle cx="50" cy="50" r="10" fill={c}/><circle cx="50" cy="50" r="20" stroke={a} strokeWidth="3" fill="none"/><circle cx="50" cy="50" r="30" stroke={c} strokeWidth="3" fill="none"/></g>; // ripple
      if (v===1) return <g><path d="M30 80 Q20 50 50 50 T70 20 M50 90 Q40 60 70 60 T90 30" stroke={c} strokeWidth="6" fill="none" opacity="0.8"/><circle cx="40" cy="80" r="8" fill={a}/></g>; // aroma
      if (v===2) return <g><path d="M30 80 L30 60 Q30 40 50 40 Q70 40 70 60 L70 80 Z" fill={c}/><circle cx="50" cy="35" r="15" fill={a}/><path d="M35 60 L35 80 M50 60 L50 80 M65 60 L65 80" stroke="#FFF" strokeWidth="3" fill="none"/></g>; // hand grasping
      if (v===3) return <g><path d="M50 20 L50 60 C50 70 30 70 30 60" stroke={c} strokeWidth="12" strokeLinecap="round" fill="none"/><circle cx="45" cy="65" r="5" fill={a}/></g>; // nose
      if (v===4) return <g><path d="M30 40 Q50 90 70 40 Z" fill={c}/><path d="M50 40 L50 70" stroke={a} strokeWidth="4"/></g>; // tongue
    case 'lifestyle_food':
      if (v===0) return <g><path d="M20 60 Q50 90 80 60 Z" fill={c}/><path d="M40 50 Q30 30 40 10 M60 50 Q70 30 60 10 M50 50 L50 20" stroke={a} strokeWidth="4" fill="none" strokeLinecap="round"/></g>; // noodles bowl
      if (v===1) return <g><path d="M30 35 L70 35 L65 75 Q50 85 35 75 Z" fill={c}/><path d="M70 45 Q85 45 85 55 Q85 65 70 65 M40 25 Q30 10 40 5 M60 25 Q50 10 60 5" stroke={a} strokeWidth="5" fill="none"/></g>; // coffee cup
      if (v===2) return <g><path d="M10 90 L80 10 M20 95 L90 15" stroke="#3A261F" strokeWidth="4"/><ellipse cx="50" cy="60" rx="6" ry="12" transform="rotate(45 50 60)" fill={c}/><ellipse cx="65" cy="45" rx="6" ry="12" transform="rotate(45 65 45)" fill={a}/></g>; // chopsticks rice
      if (v===3) return <g><rect x="30" y="40" width="40" height="20" rx="5" fill={c}/><rect x="25" y="30" width="10" height="40" rx="5" fill={a}/><rect x="65" y="30" width="10" height="40" rx="5" fill={a}/><rect x="35" y="60" width="8" height="15" fill="#3A261F"/><rect x="57" y="60" width="8" height="15" fill="#3A261F"/><path d="M30 40 Q50 20 70 40" fill={c}/></g>; // sofa chair
      if (v===4) return <g><circle cx="50" cy="50" r="35" fill={a} opacity={0.2}/><path d="M30 40 Q40 20 60 30 Q80 40 70 60 Q60 80 40 70 Q20 60 30 40 Z" fill="#FFF"/><circle cx="50" cy="50" r="12" fill={c}/></g>; // fried egg plate
    case 'retail':
      if (v===0) return <g><rect x="30" y="40" width="40" height="40" fill={c}/><path d="M40 40 C40 20 60 20 60 40" stroke={a} strokeWidth="4" fill="none"/></g>; // bag
      if (v===1) return <g><rect x="25" y="30" width="8" height="40" fill={c}/><rect x="40" y="30" width="4" height="40" fill={c}/><rect x="50" y="30" width="12" height="40" fill={a}/><rect x="68" y="30" width="6" height="40" fill={c}/></g>; // barcode
      if (v===2) return <g><path d="M30 20 L70 20 L65 80 L50 70 L35 80 Z" fill={c}/><line x1="40" y1="35" x2="60" y2="35" stroke={a} strokeWidth="3"/><line x1="40" y1="45" x2="55" y2="45" stroke={a} strokeWidth="3"/></g>; // receipt
      if (v===3) return <g><path d="M50 20 C60 20 60 35 50 35 M20 70 L50 35 L80 70" stroke={c} strokeWidth="5" fill="none"/><line x1="20" y1="70" x2="80" y2="70" stroke={a} strokeWidth="4"/></g>; // hanger
      if (v===4) return <g><rect x="30" y="40" width="40" height="40" fill={c}/><rect x="46" y="40" width="8" height="40" fill={a}/><rect x="30" y="56" width="40" height="8" fill={a}/><circle cx="45" cy="30" r="8" fill="none" stroke={a} strokeWidth="4"/><circle cx="55" cy="30" r="8" fill="none" stroke={a} strokeWidth="4"/></g>; // gift box
    case 'books_media':
      if (v===0) return <g><path d="M15 40 Q35 30 50 45 L50 85 Q35 70 15 80 Z" fill={c}/><path d="M85 40 Q65 30 50 45 L50 85 Q65 70 85 80 Z" fill={a}/></g>; // open book
      if (v===1) return <g><rect x="30" y="20" width="40" height="60" rx="8" fill={c}/><rect x="35" y="25" width="30" height="45" fill="#FFF"/><circle cx="50" cy="74" r="3" fill={a}/></g>; // mobile phone
      if (v===2) return <g><rect x="30" y="30" width="30" height="40" transform="rotate(15 45 50)" fill={c}/><polygon points="60,20 80,40 50,60" fill={a}/></g>; // bookmarks
      if (v===3) return <g><path d="M50 25 L30 85 L70 85 Z" fill={c}/><ellipse cx="50" cy="50" rx="18" ry="6" fill={a}/><path d="M50 25 L50 10 M40 10 L60 10" stroke={a} strokeWidth="4" fill="none"/></g>; // tv tower
      if (v===4) return <g><circle cx="35" cy="50" r="15" stroke={c} strokeWidth="5" fill="none"/><circle cx="65" cy="50" r="15" stroke={a} strokeWidth="5" fill="none"/><line x1="48" y1="45" x2="52" y2="45" stroke="#3A261F" strokeWidth="4"/></g>; // glasses
    case 'tech':
      if (v===0) return <g><rect x="25" y="25" width="20" height="20" fill={c}/><rect x="55" y="25" width="20" height="20" fill={a}/><rect x="25" y="55" width="20" height="20" fill={a}/><rect x="55" y="55" width="20" height="20" fill={c}/></g>; // pixels
      if (v===1) return <g><path d="M20 30 L40 30 L60 50 L80 50 M20 70 L40 70 L50 60 L70 60" stroke={c} strokeWidth="5" fill="none"/><circle cx="40" cy="30" r="5" fill={a}/><circle cx="60" cy="50" r="5" fill={a}/><circle cx="50" cy="60" r="5" fill={a}/></g>; // circuit nodes
      if (v===2) return <g><rect x="30" y="30" width="40" height="40" rx="5" fill={c}/><rect x="40" y="40" width="20" height="20" fill={a}/><line x1="25" y1="40" x2="35" y2="40" stroke="#3A261F" strokeWidth="3"/><line x1="65" y1="40" x2="75" y2="40" stroke="#3A261F" strokeWidth="3"/></g>; // chip
      if (v===3) return <g><rect x="20" y="40" width="20" height="20" fill={a}/><rect x="60" y="40" width="20" height="20" fill={a}/><circle cx="50" cy="50" r="12" fill={c}/><line x1="10" y1="50" x2="90" y2="50" stroke="#3A261F" strokeWidth="3"/></g>; // satellite
      if (v===4) return <g><path d="M40 20 L60 20 L60 40 L80 80 L20 80 L40 40 Z" fill={c}/><rect x="45" y="10" width="10" height="10" fill={a}/><path d="M25 75 L75 75" stroke="#FFF" strokeWidth="4"/></g>; // flask
    case 'tourism':
      if (v===0) return <g><polygon points="50,15 60,40 85,50 60,60 50,85 40,60 15,50 40,40" fill={c}/><circle cx="50" cy="50" r="8" fill={a}/></g>; // compass
      if (v===1) return <g><rect x="20" y="35" width="60" height="30" fill={c}/><circle cx="20" cy="50" r="6" fill="#fff"/><circle cx="80" cy="50" r="6" fill="#fff"/><line x1="60" y1="35" x2="60" y2="65" stroke={a} strokeWidth="3" strokeDasharray="4 2"/></g>; // ticket
      if (v===2) return <g><polygon points="20,70 40,50 60,60 80,40 80,70 60,90 40,80 20,90" fill={c}/><polygon points="40,50 60,60 60,90 40,80" fill={a}/></g>; // fold map
      if (v===3) return <g><path d="M50 20 C30 20 30 50 50 80 C70 50 70 20 50 20 Z" fill={c}/><circle cx="50" cy="40" r="10" fill={a}/><ellipse cx="50" cy="90" rx="15" ry="5" fill="#3A261F" opacity="0.3"/></g>; // map marker
      if (v===4) return <g><circle cx="50" cy="50" r="35" fill="none" stroke={c} strokeWidth="4" strokeDasharray="5 5"/><path d="M50 30 L70 50 L50 70 L30 50 Z" fill={a}/></g>; // stamp
    case 'gender':
      if (v===0) return <g><circle cx="50" cy="35" r="20" stroke={c} strokeWidth="8" fill="none"/><line x1="50" y1="55" x2="50" y2="85" stroke={c} strokeWidth="8"/><line x1="35" y1="70" x2="65" y2="70" stroke={a} strokeWidth="8"/></g>; // female symbol
      if (v===1) return <g><path d="M25 50 Q50 35 75 50 Q50 55 25 50" fill={c}/><path d="M25 50 Q50 75 75 50 Q50 55 25 50" fill={a}/></g>; // lips
      if (v===2) return <g><path d="M40 85 L25 45 L50 40 L75 45 L60 85 Z" fill={c}/><circle cx="30" cy="35" r="12" fill={a}/><circle cx="50" cy="25" r="14" fill={a}/><circle cx="70" cy="35" r="12" fill={a}/><path d="M30 65 L70 65" stroke={a} strokeWidth="6" fill="none"/></g>; // bouquet
      if (v===3) return <g><path d="M50 50 Q20 20 20 50 Q20 80 50 50 Q80 20 80 50 Q80 80 50 50 Z" fill={c}/><circle cx="50" cy="50" r="6" fill={a}/></g>; // ribbon
      if (v===4) return <g><polygon points="30,20 70,20 80,80 55,80 50,40 45,80 20,80" fill={c}/><rect x="30" y="20" width="40" height="10" fill={a}/><line x1="50" y1="40" x2="50" y2="70" stroke="#3A261F" strokeWidth="3"/></g>; // pants
    case 'geopolitics':
      if (v===0) return <g><circle cx="50" cy="50" r="30" fill="none" stroke={c} strokeWidth="4"/><ellipse cx="50" cy="50" rx="30" ry="10" fill="none" stroke={a} strokeWidth="3"/><ellipse cx="50" cy="50" rx="10" ry="30" fill="none" stroke={a} strokeWidth="3"/></g>; // globe grid
      if (v===1) return <g><polygon points="35,50 65,50 75,90 25,90" fill={c}/><rect x="48" y="25" width="4" height="25" fill="#3A261F"/><circle cx="50" cy="20" r="6" fill={a}/></g>; // podium mic
      if (v===2) return <g><rect x="40" y="40" width="20" height="20" rx="5" fill={c}/><line x1="20" y1="20" x2="80" y2="80" stroke="#3A261F" strokeWidth="4"/><line x1="20" y1="80" x2="80" y2="20" stroke="#3A261F" strokeWidth="4"/><circle cx="20" cy="20" r="8" fill={a}/><circle cx="80" cy="80" r="8" fill={a}/><circle cx="20" cy="80" r="8" fill={a}/><circle cx="80" cy="20" r="8" fill={a}/></g>; // drone
      if (v===3) return <g><path d="M45 40 L55 40 L60 80 L40 80 Z" fill={c}/><circle cx="50" cy="30" r="10" fill={a}/><rect x="30" y="80" width="40" height="5" fill={a}/></g>; // chess piece
      if (v===4) return <g><path d="M20 40 Q40 20 60 40 Q50 60 40 50 Q20 60 20 40 Z" fill={c}/><path d="M60 40 Q80 40 80 60 Q60 80 50 60 Q70 60 60 40 Z" fill={a}/></g>; // puzzle map
    case 'lecture':
      if (v===0) return <g><path d="M40 20 Q70 20 70 50 Q70 60 60 65 Q50 80 30 80 L30 50 L40 40 Z" fill={c}/><circle cx="50" cy="40" r="4" fill="#fff"/></g>; // profile
      if (v===1) return <g><path d="M30 40 Q30 20 55 20 Q80 20 80 40 Q80 60 65 60 L70 70 L55 60 Q30 60 30 40 Z" fill={c}/><path d="M40 60 Q20 60 20 45 Q20 35 30 35" stroke={a} strokeWidth="5" fill="none"/></g>; // speech bubble
      if (v===2) return <g><rect x="20" y="30" width="60" height="40" fill={c}/><rect x="25" y="35" width="50" height="30" fill="#3A261F"/><path d="M30 50 Q40 40 50 50 T70 50" stroke={a} strokeWidth="3" fill="none"/></g>; // blackboard
      if (v===3) return <g><rect x="25" y="55" width="20" height="8" fill={c}/><rect x="50" y="45" width="30" height="15" fill={a}/><rect x="50" y="35" width="30" height="10" fill="#3A261F"/></g>; // chalk/eraser
      if (v===4) return <g transform="rotate(45 50 50)"><polygon points="40,20 60,20 60,70 40,70" fill={c}/><polygon points="40,20 60,20 50,5" fill={a}/><polygon points="40,70 60,70 60,80 40,80" fill="#3A261F"/></g>; // pencil
    case 'taiwan_japan':
      if (v===0) return <g><rect x="25" y="30" width="50" height="6" fill={c}/><rect x="35" y="45" width="30" height="6" fill={c}/><rect x="35" y="36" width="6" height="40" fill={a}/><rect x="59" y="36" width="6" height="40" fill={a}/></g>; // torii
      if (v===1) return <g><rect x="40" y="30" width="20" height="40" rx="5" fill={c}/><circle cx="50" cy="50" r="6" fill={a}/><path d="M50 20 L50 30 M50 70 L50 80" stroke="#3A261F" strokeWidth="3"/></g>; // lantern
      if (v===2) return <g><circle cx="65" cy="35" r="20" fill={a}/><path d="M20 70 Q30 50 50 60 Q70 50 80 70 Z" fill={c}/><path d="M30 65 Q50 55 60 70" stroke="#FFF" strokeWidth="4" fill="none"/></g>; // moon and clouds
      if (v===3) return <g><path d="M30 60 Q30 30 60 40 L60 60 Z" fill={c}/><path d="M60 45 Q80 40 80 50 Q80 60 60 55" stroke={a} strokeWidth="5" fill="none"/><rect x="40" y="30" width="15" height="10" fill={a}/><rect x="15" y="50" width="12" height="10" fill={c}/></g>; // chinese teapot and teacup
      if (v===4) return <g><path d="M20 60 Q30 70 40 40 Q30 30 20 60 Z" fill={c}/><path d="M60 40 Q75 55 85 45 Q70 30 60 40 Z" fill={a}/></g>; // islands
    case 'business':
      if (v===0) return <g><polyline points="20,70 40,50 60,60 80,20" stroke={c} strokeWidth="6" fill="none"/><polygon points="75,20 85,15 85,30" fill={a}/><line x1="20" y1="20" x2="20" y2="80" stroke="#3A261F" strokeWidth="3"/><line x1="20" y1="80" x2="80" y2="80" stroke="#3A261F" strokeWidth="3"/></g>; // chart
      if (v===1) return <g><rect x="25" y="40" width="50" height="35" rx="3" fill={c}/><rect x="40" y="30" width="20" height="10" fill="none" stroke={a} strokeWidth="4"/><line x1="25" y1="50" x2="75" y2="50" stroke="#3A261F" strokeWidth="3"/></g>; // briefcase
      if (v===2) return <g><polygon points="35,10 65,10 50,50" fill={c}/><polygon points="40,25 60,25 50,40" fill={a}/><line x1="50" y1="50" x2="50" y2="80" stroke="#3A261F" strokeWidth="4"/><line x1="35" y1="80" x2="65" y2="80" stroke="#3A261F" strokeWidth="4"/></g>; // champagne glass
      if (v===3) return <g><polygon points="20,60 45,50 55,60 30,70" fill={c}/><polygon points="80,40 55,50 45,40 70,30" fill={a}/><circle cx="50" cy="50" r="5" fill="#3A261F"/></g>; // handshake
      if (v===4) return <g><rect x="25" y="30" width="40" height="50" fill={c}/><path d="M70 35 L70 70 Q70 80 60 80 Q50 80 50 70 L50 40" stroke={a} strokeWidth="5" fill="none"/><line x1="35" y1="45" x2="55" y2="45" stroke="#3A261F" strokeWidth="3"/><line x1="35" y1="55" x2="50" y2="55" stroke="#3A261F" strokeWidth="3"/></g>; // paperclip docs

    case 'drama':
      if (v===0) return <g><path d="M20 50 Q50 20 80 50 Q50 80 20 50" fill={c}/><circle cx="35" cy="45" r="4" fill={a}/><circle cx="65" cy="45" r="4" fill={a}/></g>; // theater mask
      if (v===1) return <g><rect x="30" y="20" width="40" height="60" fill={c}/><rect x="35" y="25" width="30" height="40" fill="#FFF"/><path d="M40 75 L60 75" stroke={a} strokeWidth="4"/></g>; // script
      if (v===2) return <g><path d="M10 80 L90 80 M50 80 L50 20 L20 40 M50 20 L80 40" stroke={c} strokeWidth="6" fill="none"/></g>; // stage curtains ref
      if (v===3) return <g><circle cx="50" cy="40" r="20" fill={c}/><path d="M30 70 Q50 90 70 70" stroke={a} strokeWidth="6" fill="none"/></g>; // comedy face
      if (v===4) return <g><rect x="20" y="70" width="60" height="10" fill="#3A261F"/><path d="M30 70 L30 30 Q50 10 70 30 L70 70" fill={c}/></g>; // stage door
    case 'documentary':
      if (v===0) return <g><circle cx="50" cy="50" r="30" stroke={c} strokeWidth="10" fill="none"/><rect x="45" y="30" width="10" height="40" fill={a}/></g>; // lens focus
      if (v===1) return <g><path d="M20 30 L80 30 L80 70 L20 70 Z" fill={c}/><circle cx="35" cy="50" r="10" fill={a}/></g>; // film reel
      if (v===2) return <g><rect x="30" y="20" width="40" height="60" fill={c}/><path d="M40 40 L60 40 M40 50 L60 50 M40 60 L50 60" stroke={a} strokeWidth="3"/></g>; // file folder
      if (v===3) return <g><path d="M20 80 Q50 10 80 80" stroke={c} strokeWidth="8" fill="none"/><circle cx="50" cy="40" r="8" fill={a}/></g>; // observation
      if (v===4) return <g><rect x="25" y="40" width="50" height="30" fill={c}/><rect x="75" y="45" width="10" height="20" fill={a}/></g>; // video camera
    case 'tea_alcohol':
      if (v===0) return <g><path d="M30 40 Q30 80 50 80 T70 40 Z" fill={c}/><path d="M30 40 L70 40" stroke={a} strokeWidth="4"/></g>; // wine glass
      if (v===1) return <g><rect x="40" y="30" width="20" height="50" fill={c}/><rect x="35" y="25" width="30" height="10" fill={a}/></g>; // bottle
      if (v===2) return <g><path d="M30 50 Q30 80 50 80 T70 50 L75 40 L25 40 Z" fill={c}/><path d="M40 30 Q50 20 60 30" stroke={a} strokeWidth="4" fill="none"/></g>; // tea cup
      if (v===3) return <g><circle cx="50" cy="60" r="25" fill={c}/><path d="M50 35 L50 20 M40 20 L60 20" stroke={a} strokeWidth="4"/></g>; // teapot body
      if (v===4) return <g><path d="M40 80 L30 40 L70 40 L60 80 Z" fill={c}/><circle cx="50" cy="55" r="10" fill={a}/></g>; // sake cup
    case 'parenting':
      if (v===0) return <g><circle cx="35" cy="40" r="15" fill={c}/><circle cx="65" cy="45" r="10" fill={a}/></g>; // big & small circles
      if (v===1) return <g><path d="M30 70 L70 70 L50 30 Z" fill={c}/><circle cx="50" cy="20" r="8" fill={a}/></g>; // blocks
      if (v===2) return <g><path d="M20 50 Q50 20 80 50 Q50 80 20 50" fill={c}/><path d="M40 50 C40 40 60 40 60 50" stroke={a} strokeWidth="4" fill="none"/></g>; // cradle
      if (v===3) return <g><circle cx="50" cy="50" r="20" fill={c}/><path d="M50 30 L50 10 M40 15 L60 15" stroke={a} strokeWidth="4"/></g>; // rattle
      if (v===4) return <g><path d="M30 60 Q50 30 70 60 T50 90 T30 60" fill={c}/><circle cx="50" cy="55" r="5" fill={a}/></g>; // baby bib
    case 'scholarship':
      if (v===0) return <g><rect x="30" y="30" width="40" height="30" fill={c}/><path d="M50 60 L50 80 M40 80 L60 80" stroke={a} strokeWidth="4"/></g>; // cap detail
      if (v===1) return <g><path d="M20 40 L50 20 L80 40 L50 60 Z" fill={c}/><path d="M80 40 L80 70" stroke={a} strokeWidth="4"/></g>; // grad hat top
      if (v===2) return <g><rect x="30" y="20" width="40" height="60" rx="2" fill={c}/><path d="M35 30 L65 30 M35 40 L65 40" stroke="#FFF" strokeWidth="2"/></g>; // diploma
      if (v===3) return <g><circle cx="50" cy="40" r="20" stroke={c} strokeWidth="6" fill="none"/><path d="M50 60 L50 85" stroke={a} strokeWidth="4"/></g>; // medal
      if (v===4) return <g><polygon points="50,20 60,40 80,40 65,55 70,75 50,65 30,75 35,55 20,40 40,40" fill={a}/></g>; // star
    case 'indigenous':
      if (v===0) return <g><path d="M20 50 L50 20 L80 50 L50 80 Z" stroke={c} strokeWidth="8" fill="none"/><path d="M35 50 L65 50" stroke={a} strokeWidth="6"/></g>; // diamond pattern
      if (v===1) return <g><path d="M30 20 Q50 0 70 20 L70 80 Q50 100 30 80 Z" fill={c}/><path d="M40 30 L60 30 M40 50 L60 50" stroke={a} strokeWidth="4"/></g>; // woven totem
      if (v===2) return <g><path d="M50 20 L20 80 L80 80 Z" fill={c}/><circle cx="50" cy="55" r="10" fill={a}/></g>; // mountain sun totem
      if (v===3) return <g><path d="M20 50 Q50 10 80 50" stroke={c} strokeWidth="10" fill="none"/><path d="M20 55 Q50 90 80 55" stroke={a} strokeWidth="10" fill="none"/></g>; // boat shape
      if (v===4) return <g><circle cx="50" cy="50" r="30" fill="none" stroke={c} strokeWidth="4"/><path d="M50 20 L50 80 M20 50 L80 50" stroke={a} strokeWidth="2"/></g>; // sun wheel
    case 'folklore':
      if (v===0) return <g><rect x="35" y="20" width="30" height="50" fill={c}/><path d="M35 20 Q50 5 65 20 Z" fill={a}/></g>; // lantern alt
      if (v===1) return <g><circle cx="50" cy="40" r="25" fill={c}/><path d="M35 40 L65 40 M50 25 L50 55" stroke={a} strokeWidth="4"/></g>; // ritual drum
      if (v===2) return <g><path d="M20 80 Q50 30 80 80" stroke={c} strokeWidth="12" fill="none" strokeLinecap="round"/></g>; // shrine roof
      if (v===3) return <g><path d="M30 20 L70 20 L70 70 Q50 85 30 70 Z" fill={c}/><path d="M45 35 L55 55 M55 35 L45 55" stroke={a} strokeWidth="4"/></g>; // talisman
      if (v===4) return <g><circle cx="50" cy="50" r="10" fill={c}/><path d="M50 40 Q70 20 90 40 T50 80 T10 40 T50 40" fill={a} opacity="0.6"/></g>; // lucky knot
    case 'history':
      if (v===0) return <g><rect x="25" y="30" width="50" height="40" fill={c}/><path d="M30 40 L70 40 M30 50 L70 50" stroke="#FFF" strokeWidth="2"/></g>; // stone tablet
      if (v===1) return <g><path d="M30 80 L30 30 L70 30 L70 80" stroke={c} strokeWidth="8" fill="none"/><circle cx="50" cy="45" r="10" fill={a}/></g>; // gateway
      if (v===2) return <g><path d="M20 50 Q50 10 80 50 Q50 90 20 50" fill={c}/><circle cx="50" cy="50" r="5" fill={a}/></g>; // ancient eye
      if (v===3) return <g><path d="M40 20 L60 20 L70 80 L30 80 Z" fill={c}/><rect x="45" y="30" width="10" height="30" fill={a}/></g>; // armor plate
      if (v===4) return <g><path d="M10 50 Q50 90 90 50" stroke={c} strokeWidth="8" fill="none"/><path d="M10 40 Q50 80 90 40" stroke={a} strokeWidth="8" fill="none"/></g>; // excavation layers
    case 'urban':
      if (v===0) return <g><rect x="20" y="30" width="15" height="50" fill={c}/><rect x="40" y="20" width="20" height="60" fill={a}/><rect x="65" y="40" width="15" height="40" fill={c}/></g>; // city skyline
      if (v===1) return <g><circle cx="50" cy="50" r="35" stroke={c} strokeWidth="6" fill="none"/><path d="M15 50 L85 50 M50 15 L50 85" stroke={a} strokeWidth="2"/></g>; // grid map
      if (v===2) return <g><path d="M20 80 L80 80 M50 80 L50 20" stroke={c} strokeWidth="8"/><circle cx="50" cy="30" r="12" fill={a}/></g>; // street light
      if (v===3) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><rect x="40" y="40" width="8" height="8" fill="#FFF"/><rect x="52" y="40" width="8" height="8" fill="#FFF"/></g>; // apartment block
      if (v===4) return <g><path d="M10 70 Q50 30 90 70" stroke={c} strokeWidth="10" fill="none"/><path d="M10 85 Q50 45 90 85" stroke={a} strokeWidth="10" fill="none"/></g>; // overpass
    case 'workshop':
      if (v===0) return <g><circle cx="40" cy="40" r="15" fill={c}/><path d="M50 50 L80 80" stroke={a} strokeWidth="10" strokeLinecap="round"/></g>; // magnifying tool
      if (v===1) return <g><path d="M30 20 L70 20 L70 80 L30 80 Z" fill={c}/><circle cx="50" cy="50" r="10" fill={a}/></g>; // ID badge
      if (v===2) return <g><path d="M20 50 Q50 20 80 50" stroke={c} strokeWidth="12" fill="none" strokeLinecap="round"/><circle cx="50" cy="65" r="8" fill={a}/></g>; // focus group
      if (v===3) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><path d="M30 40 L70 40 M30 60 L70 60" stroke={a} strokeWidth="4"/></g>; // toolbox
      if (v===4) return <g><path d="M50 20 L80 50 L50 80 L20 50 Z" fill={c}/><path d="M50 35 L50 65" stroke={a} strokeWidth="6"/></g>; // diamond note
    case 'literature':
      if (v===0) return <g><path d="M20 30 Q50 20 80 30 L80 80 Q50 70 20 80 Z" fill={c}/><path d="M50 30 L50 80" stroke={a} strokeWidth="4"/></g>; // open book alt
      if (v===1) return <g><path d="M40 20 L60 20 L70 90 L30 90 Z" fill={c}/><path d="M40 20 Q50 10 60 20" fill={a}/></g>; // ink bottle
      if (v===2) return <g><rect x="30" y="20" width="10" height="60" fill={c}/><rect x="45" y="20" width="10" height="60" fill={a}/><rect x="60" y="20" width="10" height="60" fill={c}/></g>; // book spines
      if (v===3) return <g><path d="M20 50 Q50 20 80 50" stroke={c} strokeWidth="4" fill="none"/><path d="M30 60 Q50 30 70 60" stroke={a} strokeWidth="4" fill="none"/></g>; // quote marks
      if (v===4) return <g><path d="M50 20 L30 80 L70 80 Z" fill={c}/><circle cx="50" cy="40" r="10" fill={a}/></g>; // fountain pen tip
    case 'tv_program':
      if (v===0) return <g><rect x="20" y="30" width="60" height="45" rx="5" fill={c}/><rect x="25" y="35" width="50" height="35" fill="#FFF"/><path d="M40 30 L30 15 M60 30 L70 15" stroke={a} strokeWidth="4"/></g>; // retro tv
      if (v===1) return <g><circle cx="50" cy="50" r="30" fill={c}/><path d="M30 50 L70 50 M50 30 L50 70" stroke={a} strokeWidth="4"/></g>; // broadcast lens
      if (v===2) return <g><rect x="25" y="45" width="50" height="10" fill={c}/><path d="M45 45 L50 20 L55 45" fill={a}/></g>; // remote control
      if (v===3) return <g><path d="M10 50 Q50 10 90 50 Q50 90 10 50" stroke={c} strokeWidth="6" fill="none"/><circle cx="50" cy="50" r="15" fill={a}/></g>; // eye icon / viewership
      if (v===4) return <g><rect x="30" y="20" width="40" height="60" fill={c}/><rect x="35" y="25" width="30" height="15" fill={a}/></g>; // clapper small
    case 'radio_program':
      if (v===0) return <g><circle cx="50" cy="50" r="20" fill={c}/><path d="M20 50 A 30 30 0 0 1 80 50" stroke={a} strokeWidth="6" fill="none"/></g>; // signal waves
      if (v===1) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><circle cx="40" cy="40" r="5" fill={a}/><circle cx="40" cy="60" r="5" fill={a}/></g>; // radio tuner
      if (v===2) return <g><path d="M50 20 L50 60" stroke={c} strokeWidth="10" strokeLinecap="round"/><circle cx="50" cy="75" r="15" fill={a}/></g>; // mic stand
      if (v===3) return <g><path d="M30 30 Q10 50 30 70 M70 30 Q90 50 70 70" stroke={c} strokeWidth="8" fill="none"/><circle cx="50" cy="50" r="10" fill={a}/></g>; // headphones
      if (v===4) return <g><rect x="20" y="40" width="60" height="20" rx="5" fill={c}/><path d="M30 40 L30 25 M70 40 L70 25" stroke={a} strokeWidth="4"/></g>; // boombox handle
    case 'exhibition':
      if (v===0) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><rect x="40" y="40" width="20" height="20" fill={a}/></g>; // pedestal
      if (v===1) return <g><path d="M20 80 L80 80 L50 20 Z" fill={c} opacity="0.6"/><path d="M40 80 L60 80 L50 40 Z" fill={a}/></g>; // spotlight
      if (v===2) return <g><rect x="25" y="25" width="50" height="50" stroke={c} strokeWidth="4" fill="none"/><circle cx="50" cy="50" r="10" fill={a}/></g>; // info placard
      if (v===3) return <g><path d="M10 50 L90 50" stroke={c} strokeWidth="8"/><circle cx="30" cy="40" r="10" fill={a}/><circle cx="70" cy="40" r="10" fill={a}/></g>; // gallery wall
      if (v===4) return <g><path d="M20 20 L80 20 L80 80 L20 80 Z" fill={c}/><path d="M30 30 L70 70" stroke={a} strokeWidth="4"/></g>; // floor plan
    case 'design_craft':
      if (v===0) return <g><circle cx="40" cy="40" r="20" stroke={c} strokeWidth="4" fill="none"/><circle cx="60" cy="60" r="20" stroke={a} strokeWidth="4" fill="none"/></g>; // interlocking rings
      if (v===1) return <g><path d="M30 20 L70 20 L50 80 Z" fill={c}/><path d="M30 20 L50 40 L70 20" stroke={a} strokeWidth="4" fill="none"/></g>; // pottery shape
      if (v===2) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><path d="M30 30 L70 70 M70 30 L30 70" stroke={a} strokeWidth="2"/></g>; // weave pattern
      if (v===3) return <g><circle cx="50" cy="50" r="30" fill={c}/><path d="M50 20 L50 80" stroke={a} strokeWidth="6"/></g>; // wood lathe / button
      if (v===4) return <g><polygon points="50,10 90,50 50,90 10,50" stroke={c} strokeWidth="4" fill="none"/><rect x="40" y="40" width="20" height="20" fill={a}/></g>; // tile design
    case 'herbal':
      if (v===0) return <g><path d="M50 80 Q30 50 50 20 Q70 50 50 80 Z" fill={c}/><path d="M50 80 L50 30" stroke={a} strokeWidth="4"/></g>; // leaf
      if (v===1) return <g><circle cx="50" cy="60" r="25" fill={c}/><path d="M50 35 L50 15" stroke={a} strokeWidth="6" strokeLinecap="round"/></g>; // mortar & pestle
      if (v===2) return <g><path d="M30 20 L70 20 L60 80 L40 80 Z" fill={c}/><path d="M30 40 L70 40" stroke={a} strokeWidth="4"/></g>; // medicine jar
      if (v===3) return <g><circle cx="50" cy="50" r="15" fill={c}/><path d="M50 35 Q70 10 90 35 M50 35 Q30 10 10 35" stroke={a} strokeWidth="4" fill="none"/></g>; // flower herb
      if (v===4) return <g><rect x="35" y="20" width="30" height="60" rx="15" fill={c}/><rect x="40" y="25" width="20" height="10" fill={a}/></g>; // test tube herb
    case 'taiwan_mandarin':
      if (v===0) return <g><rect x="30" y="30" width="40" height="40" fill={c}/><path d="M40 40 L60 60 M60 40 L40 60" stroke={a} strokeWidth="6"/></g>; // Hanzi radical style
      if (v===1) return <g><path d="M20 20 L80 20 L80 80 L20 80 Z" stroke={c} strokeWidth="8" fill="none"/><path d="M30 50 L70 50" stroke={a} strokeWidth="4"/></g>; // dictionary
      if (v===2) return <g><circle cx="50" cy="40" r="20" fill={c}/><path d="M40 70 L60 70 L50 90 Z" fill={a}/></g>; // speech bubble alt
      if (v===3) return <g><rect x="25" y="20" width="50" height="60" fill={c}/><path d="M35 30 L65 30 M35 45 L65 45" stroke="#FFF" strokeWidth="3"/></g>; // notebook
      if (v===4) return <g><path d="M10 50 Q50 10 90 50" stroke={c} strokeWidth="8" fill="none"/><circle cx="50" cy="70" r="10" fill={a}/></g>; // phonetics
    case 'healthcare':
      if (v===0) return <g><path d="M30 50 L70 50 M50 30 L50 70" stroke={c} strokeWidth="15" strokeLinecap="round"/><circle cx="50" cy="50" r="10" fill={a}/></g>; // cross
      if (v===1) return <g><path d="M20 50 Q50 10 80 50 Q50 90 20 50 Z" fill={c}/><circle cx="50" cy="50" r="12" fill={a}/></g>; // eye heal
      if (v===2) return <g><circle cx="50" cy="50" r="30" stroke={c} strokeWidth="6" fill="none"/><path d="M35 50 L65 50" stroke={a} strokeWidth="4"/></g>; // stethoscope ref
      if (v===3) return <g><rect x="30" y="30" width="40" height="40" rx="20" fill={c}/><rect x="45" y="20" width="10" height="15" fill={a}/></g>; // pill
      if (v===4) return <g><path d="M50 20 L50 80" stroke={c} strokeWidth="8"/><circle cx="50" cy="35" r="15" fill={a} opacity="0.6"/></g>; // heart pulse line
    case 'market':
      if (v===0) return <g><path d="M10 40 L90 40 L80 80 L20 80 Z" fill={c}/><path d="M30 40 Q50 10 70 40" stroke={a} strokeWidth="6" fill="none"/></g>; // basket
      if (v===1) return <g><rect x="20" y="40" width="60" height="40" fill={c}/><path d="M20 40 L50 20 L80 40" fill={a}/></g>; // stall
      if (v===2) return <g><circle cx="50" cy="50" r="30" stroke={c} strokeWidth="8" fill="none"/><path d="M50 35 L50 65 M35 50 L65 50" stroke={a} strokeWidth="4"/></g>; // coin/market
      if (v===3) return <g><path d="M30 30 L70 30 L70 80 L30 80 Z" fill={c}/><path d="M30 40 L70 40" stroke={a} strokeWidth="4"/></g>; // paper bag
      if (v===4) return <g><circle cx="40" cy="40" r="15" fill={c}/><circle cx="60" cy="60" r="15" fill={a}/></g>; // price tag circles
    case 'academic':
      if (v===0) return <g><path d="M40 30 L60 30 L55 60 L45 60 Z" fill={c}/><rect x="35" y="60" width="30" height="10" fill={a}/><circle cx="65" cy="45" r="8" stroke="#3A261F" strokeWidth="3" fill="none"/></g>; // microscope
      if (v===1) return <g><polygon points="50,30 80,45 50,60 20,45" fill={c}/><rect x="40" y="55" width="20" height="15" fill={a}/><line x1="80" y1="45" x2="80" y2="70" stroke="#3A261F" strokeWidth="3"/></g>; // grad cap
      if (v===2) return <g><rect x="40" y="30" width="20" height="40" rx="10" fill="none" stroke={c} strokeWidth="4"/><rect x="42" y="50" width="16" height="18" fill={a}/><circle cx="70" cy="65" r="4" fill={c}/><circle cx="75" cy="55" r="3" fill={c}/></g>; // test tube
      if (v===3) return <g><rect x="35" y="25" width="30" height="5" fill={c}/><rect x="40" y="30" width="20" height="45" fill={a}/><rect x="35" y="75" width="30" height="10" fill={c}/><line x1="45" y1="30" x2="45" y2="75" stroke="#FFF" strokeWidth="2"/><line x1="55" y1="30" x2="55" y2="75" stroke="#FFF" strokeWidth="2"/></g>; // column
      if (v===4) return <g><polygon points="20,70 50,70 20,40" fill={c} opacity="0.8"/><path d="M50 20 L30 80 M50 20 L70 80" stroke={a} strokeWidth="4" fill="none"/><circle cx="50" cy="20" r="4" fill="#3A261F"/></g>; // compass and triangle
    case 'competition':
      if (v===0) return <g><path d="M20 70 Q50 30 80 80 M20 55 Q50 15 80 65 M20 40 Q50 0 80 50" stroke={c} strokeWidth="6" fill="none"/><line x1="60" y1="30" x2="70" y2="80" stroke={a} strokeWidth="4"/></g>; // tracks
      if (v===1) return <g><path d="M30 30 L70 30 L60 60 L40 60 Z" fill={c}/><rect x="45" y="60" width="10" height="15" fill={a}/><rect x="35" y="75" width="30" height="5" fill="#3A261F"/><path d="M30 35 C10 35 10 55 35 45 M70 35 C90 35 90 55 65 45" stroke={a} strokeWidth="3" fill="none"/></g>; // trophy
      if (v===2) return <g><rect x="40" y="40" width="20" height="40" fill={c}/><rect x="25" y="55" width="15" height="25" fill={a}/><rect x="60" y="65" width="15" height="15" fill={a}/><circle cx="50" cy="30" r="5" fill="#3A261F"/></g>; // podium stairs
      if (v===3) return <g><path d="M50 80 C20 80 20 20 45 25 M50 80 C80 80 80 20 55 25" stroke={c} strokeWidth="4" fill="none"/><circle cx="35" cy="40" r="4" fill={a}/><circle cx="65" cy="40" r="4" fill={a}/><circle cx="35" cy="65" r="4" fill={a}/><circle cx="65" cy="65" r="4" fill={a}/></g>; // laurel
      if (v===4) return <g><circle cx="50" cy="55" r="25" fill="none" stroke={c} strokeWidth="5"/><line x1="50" y1="55" x2="60" y2="45" stroke={a} strokeWidth="4"/><rect x="45" y="20" width="10" height="6" fill={a}/><line x1="40" y1="30" x2="60" y2="30" stroke="#3A261F" strokeWidth="3"/></g>; // stopwatch
    case 'report':
      if (v===0) return <g><path d="M25 30 L65 25 L75 75 L35 80 Z" fill={c}/><polygon points="65,25 75,75 85,65 75,20" fill={a}/><line x1="35" y1="40" x2="55" y2="38" stroke="#FFF" strokeWidth="2"/><line x1="38" y1="60" x2="58" y2="58" stroke="#FFF" strokeWidth="2"/></g>; // newspaper
      if (v===1) return <g><circle cx="45" cy="45" r="18" fill="none" stroke={c} strokeWidth="6"/><line x1="58" y1="58" x2="75" y2="75" stroke={a} strokeWidth="8" strokeLinecap="round"/></g>; // magnifying glass
      if (v===2) return <g><circle cx="20" cy="80" r="5" fill={c}/><path d="M20 60 A20 20 0 0 1 40 80 M20 40 A40 40 0 0 1 60 80 M20 20 A60 60 0 0 1 80 80" stroke={a} strokeWidth="5" fill="none"/></g>; // broadcast arcs
      if (v===3) return <g><rect x="30" y="40" width="40" height="30" fill={c}/><circle cx="50" cy="55" r="8" fill={a}/><polygon points="50,10 55,30 45,30" fill={a}/><polygon points="85,35 65,40 65,30" fill={a}/><polygon points="15,35 35,40 35,30" fill={a}/></g>; // flash
      if (v===4) return <g><path d="M40 20 L60 20 L50 60 Z" fill={c}/><path d="M50 40 L50 60" stroke="#FFF" strokeWidth="2"/><circle cx="50" cy="75" r="5" fill={a}/><circle cx="50" cy="88" r="3" fill={a}/></g>; // pen nib
    default:
      return <g><path d="M20 50 Q50 20 80 50 Q50 80 20 50Z" fill={c}/><circle cx="50" cy="50" r="10" fill={a}/></g>;
  }
}

// Background organic collage base
export function getRandomCollageBase(variant: number, c: string, a: string): React.ReactNode {
  const v = variant % 5;
  if (v===0) return <g opacity="0.7"><path d="M10 20 Q30 0 60 20 T90 50 L90 80 Q60 100 30 80 T10 40 Z" fill={c}/><circle cx="70" cy="30" r="15" fill={a}/></g>;
  if (v===1) return <g opacity="0.7"><polygon points="10,40 40,10 80,30 90,70 60,90 20,80" fill={c}/><rect x="70" y="60" width="20" height="20" transform="rotate(15 80 70)" fill={a}/></g>;
  if (v===2) return <g opacity="0.7"><path d="M20 80 Q50 20 90 40 L70 90 Z" fill={c}/><circle cx="30" cy="30" r="20" fill={a}/></g>;
  if (v===3) return <g opacity="0.7"><path d="M10 50 A 40 40 0 0 1 90 50 A 30 30 0 0 0 10 50" fill={c}/><path d="M15 65 A 30 30 0 0 1 75 65 A 20 20 0 0 0 15 65" fill={a}/></g>;
  if (v===4) return <g opacity="0.7"><rect x="20" y="20" width="60" height="60" rx="30" fill={c}/><polygon points="70,10 90,30 70,50" fill={a}/></g>;
  return null;
}
