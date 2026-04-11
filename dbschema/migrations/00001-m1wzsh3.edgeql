CREATE MIGRATION m1wzsh3hn2mguiheupkhni35dumfistcmgu4k33lfk276w6rqvvmna
    ONTO initial
{
  CREATE FUTURE no_linkful_computed_splats;
  CREATE ABSTRACT TYPE default::BaseTuple {
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
  };
  CREATE TYPE default::EAVTTuple EXTENDING default::BaseTuple {
      CREATE REQUIRED PROPERTY attribute: std::str;
      CREATE REQUIRED PROPERTY entity: std::str;
      CREATE REQUIRED PROPERTY timestamp: std::datetime;
      CREATE CONSTRAINT std::exclusive ON ((.entity, .attribute, .timestamp));
      CREATE REQUIRED PROPERTY value: std::str;
  };
  CREATE TYPE default::SPOCTuple EXTENDING default::BaseTuple {
      CREATE REQUIRED PROPERTY context: std::str;
      CREATE REQUIRED PROPERTY object_: std::str;
      CREATE REQUIRED PROPERTY predicate: std::str;
      CREATE REQUIRED PROPERTY subject: std::str;
      CREATE CONSTRAINT std::exclusive ON ((.subject, .predicate, .object_, .context));
  };
};
