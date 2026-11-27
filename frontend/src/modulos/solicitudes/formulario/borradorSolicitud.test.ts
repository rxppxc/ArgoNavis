import { describe, expect, it } from "vitest";
import {
  HORAS_BORRADOR, borradorVigente, claveBorrador, cuandoSeGuardo, recuperarArchivos, restaurar, serializarArchivos,
  tieneContenido,
  type ArchivosBorrador, type ArchivosGuardados, type DatosBorrador,
} from "./borradorSolicitud";
import { fichaVacia } from "./envioSolicitud";
import { CABECERA_VACIA, type CabeceraFormulario, type FichaTripulante } from "./validacionFormulario";

const HORA = 3_600_000;
const archivo = (nombre: string) => new File(["%PDF-1.4"], nombre, { type: "application/pdf" });
const SIN_ARCHIVOS: ArchivosBorrador = { nuevos: {}, adicionales: [] };
const vacio = (): DatosBorrador => ({ codigoTramite: "", cabecera: CABECERA_VACIA, tripulantes: [fichaVacia()] });

describe("claveBorrador: uno por usuario", () => {
  it("lleva el id del usuario", () => {
    expect(claveBorrador(7)).toBe("solicitud-nueva:7");
    expect(claveBorrador(7)).not.toBe(claveBorrador(8));
  });
});

describe(`borradorVigente: ${HORAS_BORRADOR} horas desde el último cambio`, () => {
  const ahora = Date.UTC(2026, 10, 24, 15, 0);
  it("vale dentro de las 24 horas", () => {
    expect(borradorVigente(ahora - 23 * HORA, ahora)).toBe(true);
    expect(borradorVigente(ahora - 5_000, ahora)).toBe(true);
  });
  it("vence a las 24 horas", () => {
    expect(borradorVigente(ahora - 24 * HORA, ahora)).toBe(false);
    expect(borradorVigente(ahora - 30 * HORA, ahora)).toBe(false);
  });
  it("una fecha del futuro (el reloj del equipo cambió) no vale", () => {
    expect(borradorVigente(ahora + 2 * HORA, ahora)).toBe(false);
  });
});

describe("tieneContenido: solo se guarda si hay algo", () => {
  it("el formulario vacío no", () => {
    expect(tieneContenido(vacio(), SIN_ARCHIVOS)).toBe(false);
  });
  it("con un trámite elegido, un dato escrito o un archivo, sí", () => {
    expect(tieneContenido({ ...vacio(), codigoTramite: "F3-EMBARQUE" }, SIN_ARCHIVOS)).toBe(true);
    expect(tieneContenido({ ...vacio(), cabecera: { ...CABECERA_VACIA, nombre_buque: "MSC ARIES" } }, SIN_ARCHIVOS)).toBe(true);
    expect(tieneContenido({ ...vacio(), tripulantes: [{ ...fichaVacia(), nombre: "Ana" }] }, SIN_ARCHIVOS)).toBe(true);
    expect(tieneContenido(vacio(), { nuevos: { "DOC-F3|s": archivo("f3.pdf") }, adicionales: [] })).toBe(true);
  });
  it("el rango de la ficha (que trae un valor) no cuenta como dato escrito", () => {
    expect(tieneContenido({ ...vacio(), tripulantes: [fichaVacia("tecnico")] }, SIN_ARCHIVOS)).toBe(false);
  });
});

describe("restaurar: claves nuevas, con los archivos en su sitio", () => {
  it("cada tripulante recibe una clave nueva y sus archivos lo siguen", () => {
    const ana = { ...fichaVacia(), clave: "n1", nombre: "Ana" };
    const beto = { ...fichaVacia(), clave: "n2", nombre: "Beto" };
    const visaAna = archivo("visa-ana.pdf");
    const visaBeto = archivo("visa-beto.pdf");
    const lista = archivo("lista.pdf");
    const carta = archivo("carta.pdf");
    const { datos, archivos } = restaurar(
      { codigoTramite: "F3-EMBARQUE", cabecera: CABECERA_VACIA, tripulantes: [ana, beto] },
      { nuevos: { "DOC-VISA|n1": visaAna, "DOC-VISA|n2": visaBeto, "DOC-LISTA|s": lista },
        adicionales: [{ clave: "a1", archivo: carta }] },
    );
    const [nuevaAna, nuevoBeto] = datos.tripulantes;
    expect(nuevaAna.nombre).toBe("Ana");
    expect(nuevaAna.clave).not.toBe("n1");
    expect(nuevoBeto.clave).not.toBe(nuevaAna.clave);
    expect(archivos.nuevos).toEqual({
      [`DOC-VISA|${nuevaAna.clave}`]: visaAna,
      [`DOC-VISA|${nuevoBeto.clave}`]: visaBeto,
      "DOC-LISTA|s": lista,
    });
    expect(archivos.adicionales).toHaveLength(1);
    expect(archivos.adicionales[0].archivo).toBe(carta);
    expect(archivos.adicionales[0].clave).not.toBe("a1");
  });
  it("las Form. 7 de más (2026-11-27) se recuperan con su casilla", () => {
    const primera = archivo("carta-1.pdf");
    const otra = archivo("carta-2.pdf");
    const { archivos } = restaurar(
      { codigoTramite: "F3-URGENCIA-MEDICA", cabecera: CABECERA_VACIA, tripulantes: [{ ...fichaVacia(), clave: "n1" }] },
      { nuevos: { "DOC-FORM7-RESPONSABILIDAD|s": primera, "DOC-FORM7-RESPONSABILIDAD|s#o7": otra }, adicionales: [] },
    );
    expect(archivos.nuevos).toEqual({
      "DOC-FORM7-RESPONSABILIDAD|s": primera, "DOC-FORM7-RESPONSABILIDAD|s#o7": otra,
    });
  });
  it("un archivo de un tripulante que ya no está se descarta", () => {
    const { archivos } = restaurar(
      { codigoTramite: "F3-EMBARQUE", cabecera: CABECERA_VACIA, tripulantes: [{ ...fichaVacia(), clave: "n1" }] },
      { nuevos: { "DOC-VISA|n9": archivo("huerfano.pdf") }, adicionales: [] },
    );
    expect(archivos.nuevos).toEqual({});
  });
  it("sin tripulantes guardados, empieza con una ficha vacía", () => {
    const { datos } = restaurar({ codigoTramite: "", cabecera: CABECERA_VACIA, tripulantes: [] }, SIN_ARCHIVOS);
    expect(datos.tripulantes).toHaveLength(1);
  });
  it("lo guardado por la versión anterior recibe vacíos los campos nuevos", () => {
    // Un despliegue con un campo nuevo, mientras alguien tenía un borrador a medias.
    const fichaVieja: Partial<FichaTripulante> = { ...fichaVacia(), clave: "n1", nombre: "Ana" };
    delete fichaVieja.pasaporte;
    const cabeceraVieja: Partial<CabeceraFormulario> = { ...CABECERA_VACIA, nombre_buque: "ESTRELLA" };
    delete cabeceraVieja.fecha_operacion;
    const { datos } = restaurar(
      { codigoTramite: "F3-EMBARQUE", cabecera: cabeceraVieja as CabeceraFormulario,
        tripulantes: [fichaVieja as FichaTripulante] },
      SIN_ARCHIVOS,
    );
    expect(datos.tripulantes[0]).toMatchObject({ nombre: "Ana", pasaporte: "" });
    expect(datos.cabecera).toMatchObject({ nombre_buque: "ESTRELLA", fecha_operacion: "" });
  });
});

describe("los archivos se guardan como su contenido y vuelven como File", () => {
  it("con su nombre, su tipo, su fecha y su contenido", async () => {
    const original = new File(["%PDF-1.4 hola"], "formulario-3.pdf", { type: "application/pdf", lastModified: 1_700_000_000_000 });
    const guardados = await serializarArchivos({
      nuevos: { "DOC-F3|s": original }, adicionales: [{ clave: "a1", archivo: archivo("carta.pdf") }],
    });
    // Lo que va a IndexedDB no lleva ningún File: solo datos y el contenido.
    expect(guardados.nuevos["DOC-F3|s"].contenido).toBeInstanceOf(ArrayBuffer);

    const vuelta = recuperarArchivos(structuredClone(guardados));
    const f = vuelta.nuevos["DOC-F3|s"];
    expect(f).toBeInstanceOf(File);
    expect([f.name, f.type, f.lastModified, f.size]).toEqual(["formulario-3.pdf", "application/pdf", 1_700_000_000_000, original.size]);
    expect(await f.text()).toBe("%PDF-1.4 hola");
    expect(vuelta.adicionales[0].clave).toBe("a1");
    expect(vuelta.adicionales[0].archivo.name).toBe("carta.pdf");
  });
  it("lo guardado como File por la primera versión (72028b0) se recupera igual", async () => {
    const viejo = archivo("formulario-3.pdf");
    const vuelta = recuperarArchivos({ nuevos: { "DOC-F3|s": viejo }, adicionales: [] } as unknown as ArchivosGuardados);
    expect(vuelta.nuevos["DOC-F3|s"].name).toBe("formulario-3.pdf");
    expect(await vuelta.nuevos["DOC-F3|s"].text()).toBe("%PDF-1.4");
  });
});

describe("cuandoSeGuardo: para el aviso al volver", () => {
  const ahora = new Date(2026, 10, 24, 15, 30);
  it("hoy, con la hora", () => {
    expect(cuandoSeGuardo(new Date(2026, 10, 24, 10, 42).getTime(), ahora)).toBe("hoy a las 10:42 a. m.");
    expect(cuandoSeGuardo(new Date(2026, 10, 24, 12, 5).getTime(), ahora)).toBe("hoy a las 12:05 p. m.");
  });
  it("ayer", () => {
    expect(cuandoSeGuardo(new Date(2026, 10, 23, 16, 5).getTime(), ahora)).toBe("ayer a las 4:05 p. m.");
  });
  it("antes de ayer, con la fecha", () => {
    expect(cuandoSeGuardo(new Date(2026, 10, 22, 0, 15).getTime(), ahora)).toBe("el 22/11/2026 a las 12:15 a. m.");
  });
});
