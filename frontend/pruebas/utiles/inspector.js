/**
 * Sondas de maquetacion y accesibilidad que se ejecutan dentro del navegador.
 *
 * Cada una devuelve la LISTA de elementos culpables, no un booleano. Un
 * `expect(hayDesborde).toBe(false)` dice que algo se sale; una lista con el
 * selector y los pixeles que sobran dice cual y cuanto, que es lo unico que
 * permite arreglarlo sin volver a reproducir el fallo a mano.
 *
 * Las sondas se instalan una sola vez por documento en `window.__revoSondas`.
 * Se hace con `page.evaluate` y no con `addInitScript` para que funcionen
 * aunque la pagina ya este cargada, y son idempotentes: cada helper llama a
 * `asegurarSondas` sin preocuparse de si ya estaban.
 */

const FUENTE_SONDAS = () => {
  if (window.__revoSondas) return

  // Un `span` sin clase no se puede buscar en el editor. El descriptor
  // sube por los ancestros hasta encontrar uno con clase o id, para que el
  // informe diga donde vive el elemento y no solo como se llama.
  const nombreCorto = (el) => {
    const clases = typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.')
      : ''
    const id = el.id ? '#' + el.id : ''
    return el.tagName.toLowerCase() + id + clases
  }

  const describir = (el) => {
    const cadena = [nombreCorto(el)]
    let padre = el.parentElement
    let saltos = 0
    while (padre && padre !== document.body && saltos < 4) {
      const nombre = nombreCorto(padre)
      cadena.unshift(nombre)
      if (padre.id || (typeof padre.className === 'string' && padre.className.trim())) break
      padre = padre.parentElement
      saltos += 1
    }
    const texto = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40)
    return cadena.join(' > ') + (texto ? ` "${texto}"` : '')
  }

  /**
   * Oculto solo para la vista: el patron estandar de texto que anuncian los
   * lectores de pantalla y que nadie ve (caja de 1px con el contenido
   * recortado). Esta pintado y ocupa sitio en el arbol, asi que pasa
   * cualquier comprobacion ingenua de visibilidad, pero medir su
   * maquetacion no tiene sentido: el recorte es el objetivo, no un fallo.
   */
  const soloParaLector = (el, estilo) => {
    const recortado = estilo.clip === 'rect(0px, 0px, 0px, 0px)'
      || /inset\(\s*50%/.test(estilo.clipPath)
    const minusculo = el.getBoundingClientRect().width <= 1
      && el.getBoundingClientRect().height <= 1
    return recortado && minusculo
  }

  const visible = (el, estilo) =>
    estilo.display !== 'none'
    && estilo.visibility !== 'hidden'
    && estilo.opacity !== '0'
    && !soloParaLector(el, estilo)

  /**
   * Decorativo = fuera del arbol de accesibilidad y sin interaccion.
   *
   * Se mira el ancestro y no solo el elemento: `aria-hidden` se hereda, y
   * los adornos de REVO son contenedores marcados con `aria-hidden` llenos
   * de `<span>` sueltos. Sin subir por el arbol, cada hijo de un adorno se
   * cuenta como un fallo de maquetacion.
   */
  const decorativo = (el) => {
    if (el.closest('[aria-hidden="true"]')) return true
    let actual = el
    while (actual && actual !== document.body) {
      const estilo = getComputedStyle(actual)
      if (estilo.pointerEvents === 'none' && estilo.position !== 'static') return true
      actual = actual.parentElement
    }
    return false
  }

  window.__revoSondas = {
    describir,

    /**
     * Contenido que se sale de la ventana.
     *
     * Solo cuenta lo que el usuario tiene que poder leer o pulsar: texto
     * propio y controles. Las ilustraciones de REVO se posicionan a
     * proposito medio fuera del borde (`right: -7%`), y marcarlas como
     * fallo entierra los hallazgos de verdad bajo ruido de diseno.
     */
    desbordados(tolerancia) {
      const ancho = document.documentElement.clientWidth
      const fuera = []
      const interactivo = 'a[href], button, input, select, textarea, [role=button], [role=radio]'

      for (const el of document.querySelectorAll('body *')) {
        const estilo = getComputedStyle(el)
        if (!visible(el, estilo)) continue
        if (decorativo(el)) continue

        const tieneTextoPropio = [...el.childNodes]
          .some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim())
        const esControl = el.matches(interactivo)
        if (!tieneTextoPropio && !esControl) continue

        const r = el.getBoundingClientRect()
        if (r.width === 0 || r.height === 0) continue

        const sobraDerecha = r.right - ancho
        const sobraIzquierda = -r.left
        if (sobraDerecha > tolerancia || sobraIzquierda > tolerancia) {
          fuera.push({
            elemento: describir(el),
            sobraDerecha: Math.round(sobraDerecha),
            sobraIzquierda: Math.round(sobraIzquierda),
            ancho: Math.round(r.width),
          })
        }
      }
      // Un contenedor desbordado arrastra a todos sus hijos. Se ordena por
      // exceso y se recortan los diez peores para que el informe sea legible.
      return fuera.sort((a, b) => b.sobraDerecha - a.sobraDerecha).slice(0, 10)
    },

    /**
     * Controles por debajo del area tactil minima.
     *
     * Aplica las dos excepciones que la propia WCAG 2.5.8 reconoce, sin
     * las cuales la sonda marca como fallo cosas que no lo son:
     *
     *   - Enlace en linea: un enlace dentro de una frase esta limitado por
     *     el interlineado del texto que lo rodea, no por el diseno.
     *   - Control con etiqueta: una casilla de 17px envuelta en un <label>
     *     se activa pulsando toda la etiqueta, asi que el area real es la
     *     de la etiqueta.
     */
    tactilesPequenos(minimo) {
      const seleccion = [
        'a[href]', 'button', 'input:not([type=hidden])', 'select', 'textarea',
        '[role=button]', '[role=radio]', '[role=checkbox]', '[tabindex]:not([tabindex="-1"])',
      ].join(', ')
      const pequenos = []

      const enLinea = (el) => {
        if (el.tagName !== 'A') return false
        const padre = el.parentElement
        if (!padre) return false
        return [...padre.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim())
      }

      const areaEfectiva = (el) => {
        const r = el.getBoundingClientRect()
        const etiqueta = el.closest('label')
          || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`))
        if (!etiqueta) return r
        const re = etiqueta.getBoundingClientRect()
        return {
          width: Math.max(r.width, re.width),
          height: Math.max(r.height, re.height),
          top: Math.min(r.top, re.top),
          bottom: Math.max(r.bottom, re.bottom),
        }
      }

      for (const el of document.querySelectorAll(seleccion)) {
        const estilo = getComputedStyle(el)
        if (!visible(el, estilo)) continue
        if (el.disabled) continue
        if (enLinea(el)) continue

        const r = el.getBoundingClientRect()
        if (r.width === 0 || r.height === 0) continue
        // Fuera de la ventana: se mide lo que el dedo puede alcanzar ahora.
        if (r.bottom < 0 || r.top > window.innerHeight) continue

        const area = areaEfectiva(el)
        if (area.width < minimo || area.height < minimo) {
          pequenos.push({
            elemento: describir(el),
            ancho: Math.round(area.width),
            alto: Math.round(area.height),
          })
        }
      }
      return pequenos
    },

    textoRecortado(tolerancia) {
      const recortados = []

      for (const el of document.querySelectorAll('body *')) {
        if (!el.textContent?.trim()) continue
        if (el.children.length > 0) continue

        const estilo = getComputedStyle(el)
        if (!visible(el, estilo)) continue

        // Solo se pierde texto cuando la caja lo recorta. Con el
        // `overflow: visible` por defecto el contenido que se sale del
        // borde se sigue pintando entero, y `scrollHeight` supera a
        // `clientHeight` por el redondeo del interlineado en casi
        // cualquier titular: medir eso da falsos positivos a docenas.
        const recortaX = /hidden|clip/.test(estilo.overflowX)
        const recortaY = /hidden|clip/.test(estilo.overflowY)
        if (!recortaX && !recortaY) continue

        // Recortes deliberados y anunciados.
        if (estilo.textOverflow === 'ellipsis') continue
        if (estilo.webkitLineClamp && estilo.webkitLineClamp !== 'none') continue

        const excesoX = recortaX ? el.scrollWidth - el.clientWidth : 0
        const excesoY = recortaY ? el.scrollHeight - el.clientHeight : 0
        if (excesoX > tolerancia || excesoY > tolerancia) {
          recortados.push({ elemento: describir(el), excesoX, excesoY })
        }
      }
      return recortados.slice(0, 10)
    },

    imagenesSinReserva() {
      return [...document.querySelectorAll('img')]
        .filter((img) => {
          const estilo = getComputedStyle(img)
          const tieneAtributos = img.hasAttribute('width') && img.hasAttribute('height')
          const tieneRatio = estilo.aspectRatio && estilo.aspectRatio !== 'auto'
          const tieneAltoFijo = estilo.height !== 'auto' && !estilo.height.startsWith('0')
          return !tieneAtributos && !tieneRatio && !tieneAltoFijo
        })
        .map((img) => ({ elemento: describir(img), src: (img.getAttribute('src') || '').slice(-60) }))
    },

    imagenesSinAlt() {
      return [...document.querySelectorAll('img')]
        .filter((img) => !img.hasAttribute('alt'))
        .map((img) => ({ elemento: describir(img), src: (img.getAttribute('src') || '').slice(-60) }))
    },

    imagenesRotas() {
      return [...document.querySelectorAll('img')]
        .filter((img) => img.complete && img.naturalWidth === 0 && img.getAttribute('src'))
        .map((img) => ({ elemento: describir(img), src: img.getAttribute('src') }))
    },

    encabezados() {
      const niveles = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')]
        .filter((h) => visible(h, getComputedStyle(h)))
        .map((h) => ({ nivel: Number(h.tagName[1]), texto: (h.textContent || '').trim().slice(0, 50) }))

      const saltos = []
      let previo = 0
      for (const h of niveles) {
        if (previo && h.nivel > previo + 1) saltos.push({ de: `h${previo}`, a: `h${h.nivel}`, texto: h.texto })
        previo = h.nivel
      }
      return { total: niveles.length, h1: niveles.filter((h) => h.nivel === 1).length, saltos }
    },

    camposSinEtiqueta() {
      const huerfanos = []
      for (const campo of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
        if (!visible(campo, getComputedStyle(campo))) continue
        const tieneAria = campo.getAttribute('aria-label') || campo.getAttribute('aria-labelledby')
        const tienePorId = campo.id && document.querySelector(`label[for="${CSS.escape(campo.id)}"]`)
        const tienePorEnvoltura = campo.closest('label')
        const tieneTitle = campo.getAttribute('title')
        if (!tieneAria && !tienePorId && !tienePorEnvoltura && !tieneTitle) {
          huerfanos.push({ elemento: describir(campo), tipo: campo.type || campo.tagName })
        }
      }
      return huerfanos
    },

    /** Controles cuyo unico contenido es un icono, sin nombre accesible. */
    botonesSinNombre() {
      const sinNombre = []
      for (const el of document.querySelectorAll('button, a[href], [role=button]')) {
        if (!visible(el, getComputedStyle(el))) continue
        const texto = (el.innerText || '').trim()
        const aria = el.getAttribute('aria-label') || el.getAttribute('title')
        const etiquetadoPorOtro = el.getAttribute('aria-labelledby')
        const imagenConAlt = [...el.querySelectorAll('img[alt]')].some((i) => i.alt.trim())
        // Un texto que solo son simbolos (flechas, puntos) no nombra nada.
        const textoUtil = texto.replace(/[^\p{L}\p{N}]/gu, '').length > 0
        if (!textoUtil && !aria && !etiquetadoPorOtro && !imagenConAlt) {
          sinNombre.push({ elemento: describir(el), contenido: texto.slice(0, 20) })
        }
      }
      return sinNombre
    },

    /** Superposiciones: elementos interactivos tapados en su punto central. */
    controlesTapados() {
      const tapados = []
      for (const el of document.querySelectorAll('button, a[href], input:not([type=hidden])')) {
        const estilo = getComputedStyle(el)
        if (!visible(el, estilo)) continue
        const r = el.getBoundingClientRect()
        if (r.width === 0 || r.height === 0) continue
        if (r.top < 0 || r.bottom > window.innerHeight) continue

        const x = r.left + r.width / 2
        const y = r.top + r.height / 2
        const encima = document.elementFromPoint(x, y)
        if (encima && encima !== el && !el.contains(encima) && !encima.contains(el)) {
          tapados.push({ elemento: describir(el), tapadoPor: describir(encima) })
        }
      }
      return tapados
    },
  }
}

async function asegurarSondas(page) {
  await page.evaluate(FUENTE_SONDAS)
}

const sonda = (nombre) => async (page, ...args) => {
  await asegurarSondas(page)
  return page.evaluate(
    ({ nombre, args }) => window.__revoSondas[nombre](...args),
    { nombre, args },
  )
}

/**
 * Elementos que sobresalen del ancho de la ventana.
 * La tolerancia de 1px absorbe el redondeo subpixel de los bordes.
 */
export const elementosDesbordados = (page, tolerancia = 1) => sonda('desbordados')(page, tolerancia)

/**
 * Controles con area tactil por debajo del minimo.
 * 24x24 px CSS es el minimo de la WCAG 2.2 (criterio 2.5.8, nivel AA);
 * 44x44 es el nivel AAA y la recomendacion de Apple.
 */
export const objetivosTactilesPequenos = (page, minimo = 24) => sonda('tactilesPequenos')(page, minimo)

/** Texto recortado sin forma de verlo (ni scroll ni puntos suspensivos). */
export const textoRecortado = (page, tolerancia = 2) => sonda('textoRecortado')(page, tolerancia)

/** Imagenes sin hueco reservado: la causa habitual de saltos de maquetacion. */
export const imagenesSinReserva = (page) => sonda('imagenesSinReserva')(page)

/** Imagenes sin atributo alt (ni siquiera `alt=""` para las decorativas). */
export const imagenesSinAlt = (page) => sonda('imagenesSinAlt')(page)

/** Imagenes cuyo src no cargo. */
export const imagenesRotas = (page) => sonda('imagenesRotas')(page)

/** Recuento de encabezados y saltos de nivel (h1 -> h3). */
export const encabezados = (page) => sonda('encabezados')(page)

/** Campos de formulario sin etiqueta accesible de ningun tipo. */
export const camposSinEtiqueta = (page) => sonda('camposSinEtiqueta')(page)

/** Botones y enlaces sin nombre accesible. */
export const botonesSinNombre = (page) => sonda('botonesSinNombre')(page)

/** Controles tapados por otro elemento en su punto central. */
export const controlesTapados = (page) => sonda('controlesTapados')(page)

/** Cuanto se puede desplazar la pagina en horizontal (deberia ser cero). */
export async function desplazamientoHorizontal(page) {
  return page.evaluate(() => {
    const d = document.documentElement
    return { scrollWidth: d.scrollWidth, clientWidth: d.clientWidth, exceso: d.scrollWidth - d.clientWidth }
  })
}

/** Convierte una lista de hallazgos en un mensaje legible para el informe. */
export function detallar(titulo, hallazgos) {
  if (!hallazgos.length) return titulo
  const lineas = hallazgos.map((h) => '  - ' + JSON.stringify(h)).join('\n')
  return `${titulo} (${hallazgos.length}):\n${lineas}`
}
