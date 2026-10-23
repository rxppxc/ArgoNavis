import { describe, expect, it } from "vitest";
import { documentoDePrueba, solicitudDePrueba, tripulanteDePrueba } from "../../pruebas/datos";
import { claveCasilla, type CasillaFormulario } from "./checklist";
import { armarEnvio, desdeSolicitud, fichaVacia, type DocumentosElegidos } from "./envioSolicitud";
import { CABECERA_VACIA, type CabeceraFormulario, type FichaTripulante } from "./validacionFormulario";

const pdf = (nombre: string) => new File(["%PDF-1.4"], nombre, { type: "application/pdf" });

function casilla(documentoCodigo: string, claveTripulante: string | null = null): CasillaFormulario {
  return {
    clave: claveCasilla(documentoCodigo, claveTripulante), documento_codigo: documentoCodigo,
    documento_nombre: documentoCodigo, descripcion: null,
    clave_tripulante: claveTripulante, nombre_tripulante: claveTripulante,
  };
}

const SIN_DOCUMENTOS: DocumentosElegidos = {
  casillas: [], nuevos: {}, existentes: {}, adicionalesNuevos: [], adicionalesExistentes: [],
};

describe("desdeSolicitud: la precarga de una solicitud devuelta", () => {
  const precarga = desdeSolicitud(solicitudDePrueba({
    puesto_control_id: 7, fecha_operacion: "2026-11-02", nombre_buque: "ESTRELLA DEL ISTMO", imo: "9074729",
    bandera: "PAN", observaciones: "Las de cuando se envió",
    tripulantes: [tripulanteDePrueba({ id: 11, nombre: "Ana", rango: "tecnico", libreta_marino: null, libreta_expira: null })],
    documentos: [
      documentoDePrueba({ id: 1, documento_codigo: "LISTA" }),
      documentoDePrueba({ id: 2, documento_codigo: "VISA", tripulante_id: 11 }),
      documentoDePrueba({ id: 3, documento_codigo: "VISA", tripulante_id: 11 }),
      documentoDePrueba({ id: 4, documento_codigo: null, documento_id: null }),
    ],
  }));

  it("pasa los datos a la cabecera; las observaciones empiezan vacías (son las de la corrección)", () => {
    expect(precarga.cabecera).toEqual<CabeceraFormulario>({
      ...CABECERA_VACIA, puesto_control_id: "7", fecha_operacion: "2026-11-02",
      nombre_buque: "ESTRELLA DEL ISTMO", imo: "9074729", bandera: "PAN",
    });
  });

  it("conserva el id de cada tripulante, que da su clave", () => {
    expect(precarga.tripulantes).toEqual([expect.objectContaining({
      clave: "t11", id: 11, nombre: "Ana", rango: "tecnico", libreta_marino: "", libreta_expira: "",
    })]);
  });

  it("agrupa los documentos cargados por casilla y aparta los adicionales", () => {
    expect(Object.keys(precarga.existentes).sort()).toEqual([claveCasilla("LISTA", null), claveCasilla("VISA", "t11")].sort());
    expect(precarga.existentes[claveCasilla("VISA", "t11")].map((d) => d.id)).toEqual([2, 3]);
    expect(precarga.adicionales.map((d) => d.id)).toEqual([4]);
  });
});

describe("armarEnvio: lo que se manda al servidor", () => {
  const ana: FichaTripulante = {
    ...fichaVacia(), clave: "t11", id: 11, nombre: " Ana ", apellido: " Ríos ", pasaporte: " P123 ",
    libreta_marino: " SB-1 ", libreta_expira: "2030-01-01", ocupacion: " Cocinera ",
  };
  const beto: FichaTripulante = {
    ...fichaVacia("tecnico"), clave: "n2", nombre: "Beto", libreta_marino: "SB-9", libreta_expira: "2030-01-01",
  };

  it("cada archivo va con su asignación y en el mismo orden: el checklist y después los adicionales", () => {
    const lista = casilla("LISTA");
    const visaAna = casilla("VISA", "t11");
    const visaBeto = casilla("VISA", "n2");
    const archivos = [pdf("lista.pdf"), pdf("visa-ana.pdf"), pdf("visa-beto.pdf"), pdf("carta.pdf")];
    const envio = armarEnvio(CABECERA_VACIA, [beto, ana], {
      ...SIN_DOCUMENTOS,
      casillas: [lista, visaAna, visaBeto],
      nuevos: { [visaBeto.clave]: archivos[2], [lista.clave]: archivos[0], [visaAna.clave]: archivos[1] },
      adicionalesNuevos: [{ clave: "a1", archivo: archivos[3] }],
    });
    expect(envio.archivos).toEqual(archivos);
    // El índice del tripulante es su posición en la lista que se envía.
    expect(envio.datos.asignaciones).toEqual([
      { documento_codigo: "LISTA", indice_tripulante: null },
      { documento_codigo: "VISA", indice_tripulante: 1 },
      { documento_codigo: "VISA", indice_tripulante: 0 },
      { documento_codigo: null, indice_tripulante: null },
    ]);
  });

  it("solo manda los archivos nuevos: lo ya cargado no se vuelve a subir", () => {
    const lista = casilla("LISTA");
    const envio = armarEnvio(CABECERA_VACIA, [ana], {
      ...SIN_DOCUMENTOS, casillas: [lista], existentes: { [lista.clave]: [documentoDePrueba({ id: 1 })] },
    });
    expect(envio.archivos).toEqual([]);
    expect(envio.datos.asignaciones).toEqual([]);
  });

  it("normaliza el IMO, recorta los textos y deja nulos los vacíos", () => {
    const { datos } = armarEnvio(
      { ...CABECERA_VACIA, puesto_control_id: "3", imo: " imo 9074729 ", nombre_buque: "  ", motivo: " Compras " },
      [ana], SIN_DOCUMENTOS,
    );
    expect(datos).toMatchObject({
      puesto_control_id: 3, imo: "9074729", nombre_buque: null, motivo: "Compras",
      fecha_operacion: null, bandera: null, observaciones: null,
    });
    expect(datos.tripulantes[0]).toMatchObject({
      id: 11, nombre: "Ana", apellido: "Ríos", pasaporte: "P123", ocupacion: "Cocinera",
    });
  });

  it("un IMO que no es válido va tal cual: el servidor responde con su mensaje", () => {
    expect(armarEnvio({ ...CABECERA_VACIA, imo: " IMO 9074728 " }, [ana], SIN_DOCUMENTOS).datos.imo).toBe("IMO 9074728");
  });

  it("el seamanbook va solo en los rangos que lo portan; los tripulantes nuevos van sin id", () => {
    const { datos } = armarEnvio(CABECERA_VACIA, [ana, beto], SIN_DOCUMENTOS);
    expect(datos.tripulantes.map((t) => [t.id, t.libreta_marino, t.libreta_expira])).toEqual([
      [11, "SB-1", "2030-01-01"],
      [null, null, null],
    ]);
  });

  it("al corregir conserva lo que no se reemplazó, salvo lo de casillas que ya no se piden", () => {
    const lista = casilla("LISTA");
    const visaAna = casilla("VISA", "t11");
    const { conservados } = armarEnvio(CABECERA_VACIA, [ana], {
      ...SIN_DOCUMENTOS,
      casillas: [lista, visaAna],
      nuevos: { [visaAna.clave]: pdf("visa-nueva.pdf") },
      existentes: {
        [lista.clave]: [documentoDePrueba({ id: 1 })],
        [visaAna.clave]: [documentoDePrueba({ id: 2 })],
        // De un tripulante que se quitó del formulario.
        [claveCasilla("VISA", "t12")]: [documentoDePrueba({ id: 3 })],
      },
      adicionalesExistentes: [documentoDePrueba({ id: 9, documento_codigo: null, documento_id: null })],
    });
    expect(conservados).toEqual([1, 9]);
  });
});
